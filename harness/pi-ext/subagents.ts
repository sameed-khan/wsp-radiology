import { spawn, type ChildProcess } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync, openSync, closeSync, writeSync, writeFileSync, readFileSync, existsSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { StringDecoder } from "node:string_decoder";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const MODEL = "anthropic/claude-haiku-5-5";
const LIMIT = 8;
const MAX_RESULT = 20000;
const containerTools = join(dirname(fileURLToPath(import.meta.url)), "container-tools.ts");
type Job = { id: string; task: string; policy: string; state: "queued" | "running" | "completed" | "failed"; text: string; error?: string; child?: ChildProcess; done: Promise<void>; finish: () => void };

export default function (pi: ExtensionAPI) {
  const jobs = new Map<string, Job>();
  const queue: Job[] = [];
  let running = 0, stopped = false;
  const recorder = process.env.WSP_RECORDER_DIR;
  const deadline = Number(process.env.WSP_DEADLINE_EPOCH);
  if (!recorder || !Number.isFinite(deadline) || deadline <= 0 || !process.env.WSP_CONTAINER || !process.env.WSP_EXEC_USER) {
    throw new Error("subagents require WSP_RECORDER_DIR, WSP_DEADLINE_EPOCH, WSP_CONTAINER and WSP_EXEC_USER");
  }
  const dir = resolve(recorder, "subagents");
  mkdirSync(dir, { recursive: true, mode: 0o700 });
  const currentDeadline = () => {
    try {
      const value = JSON.parse(readFileSync(process.env.WSP_DEADLINE_FILE!, "utf8")).deadline_epoch;
      if (typeof value === "number" && Number.isFinite(value) && value > 0) return value;
    } catch { /* fall back to launch deadline */ }
    return deadline;
  };
  const outageActive = () => !!process.env.WSP_DEADLINE_FILE && existsSync(join(dirname(process.env.WSP_DEADLINE_FILE), "rate-limit-outage.json"));
  const expired = () => !outageActive() && Date.now() >= currentDeadline() * 1000;
  function finish(job: Job, error?: string) {
    if (job.state === "completed" || job.state === "failed") return;
    if (job.state === "running") running--;
    job.error = error; job.state = error ? "failed" : "completed";
    job.finish(); pump();
  }
  function terminate() {
    stopped = true;
    for (const job of queue.splice(0)) finish(job, "Session ended or deadline reached");
    for (const job of jobs.values()) if (job.state === "running") {
      job.error = "Session ended or deadline reached";
      const child = job.child;
      const killGroup = (signal: NodeJS.Signals) => { if (child?.pid) { try { process.kill(-child.pid, signal); } catch { /* already gone */ } } };
      killGroup("SIGTERM");
      const timer = setTimeout(() => killGroup("SIGKILL"), 2000); timer.unref();
    }
  }
  let timer: NodeJS.Timeout | undefined;
  function scheduleDeadline() {
    const remaining = currentDeadline() * 1000 - Date.now();
    if (remaining <= 0 && !outageActive()) { terminate(); return; }
    timer = setTimeout(scheduleDeadline, Math.max(1, Math.min(remaining > 0 ? remaining : 1000, 1000)));
    timer.unref();
  }
  function pump() {
    if (stopped || expired()) { if (!stopped) terminate(); return; }
    while (running < LIMIT && queue.length) {
      const job = queue.shift()!;
      job.state = "running"; running++;
      let out: number | undefined, err: number | undefined;
      try {
        const prefix = join(dir, job.id);
        // The parent's system prompt includes the arm's study rules; the child
        // has its own strictly limited tool declarations regardless of this text.
        writeFileSync(`${prefix}.policy.txt`, job.policy, { mode: 0o600, flag: "wx" });
        out = openSync(`${prefix}.events.jsonl`, "wx", 0o600);
        err = openSync(`${prefix}.stderr.log`, "wx", 0o600);
        const child = spawn("pi", ["--mode", "json", "-p", "--model", MODEL, "--thinking", "medium", "--session-dir", dir, "--session-id", job.id, "--no-extensions", "-e", containerTools, "--no-skills", "--no-context-files", "--no-prompt-templates", "--no-themes", "--no-mcp", "--tools", "read,write,edit,bash", "--append-system-prompt", `${prefix}.policy.txt`, "--", job.task], { stdio: ["ignore", "pipe", "pipe"], detached: true });
        job.child = child;
        let pending = "";
        const decoder = new StringDecoder("utf8");
        child.stdout!.on("data", (chunk: Buffer) => {
          writeSync(out!, chunk);
          pending += decoder.write(chunk);
          const lines = pending.split("\n"); pending = lines.pop()!;
          for (const line of lines) try {
            const event = JSON.parse(line);
            if (event.type === "message_end" && event.message?.role === "assistant") {
              const msg = event.message;
              if (msg.stopReason === "error" || msg.stopReason === "aborted") job.error = `Child ${msg.stopReason}: ${msg.errorMessage || "unknown error"}`;
              else { if (!stopped) job.error = undefined; job.text = (msg.content || []).filter((c: any) => c.type === "text").map((c: any) => c.text).join("\n"); }
            }
          } catch { /* raw stream remains authoritative */ }
        });
        child.stderr!.on("data", (chunk: Buffer) => writeSync(err!, chunk));
        child.on("error", e => { job.error = `Cannot start child: ${e.message}`; });
        child.on("close", code => {
          closeSync(out!); closeSync(err!);
          finish(job, job.error || (code !== 0 ? `Child exited with status ${code}` : undefined));
        });
      } catch (e) {
        if (out !== undefined) closeSync(out); if (err !== undefined) closeSync(err);
        finish(job, `Cannot launch child: ${String(e)}`);
      }
    }
  }
  function result(job: Job) {
    const text = job.text.length > MAX_RESULT ? job.text.slice(0, MAX_RESULT) + "\n[Truncated; full output in recorder.]" : job.text;
    return { content: [{ type: "text" as const, text: JSON.stringify({ id: job.id, status: job.state, ...(job.error ? { error: job.error } : {}), ...(job.state === "completed" ? { text } : {}) }) }], details: { id: job.id, status: job.state }, ...(job.error ? { isError: true } : {}) };
  }
  async function wait(job: Job, signal?: AbortSignal) {
    if (!signal) return job.done;
    if (signal.aborted) throw new Error("Aborted while waiting; child continues until deadline");
    await new Promise<void>((resolve, reject) => {
      const abort = () => { signal.removeEventListener("abort", abort); reject(new Error("Aborted while waiting; child continues until deadline")); };
      signal.addEventListener("abort", abort, { once: true });
      job.done.then(() => { signal.removeEventListener("abort", abort); resolve(); });
    });
  }
  pi.registerTool({ name: "subagent", label: "Haiku subagent", description: "Start a Haiku-only child in the same container. Set wait=false for asynchronous execution; no model selection is allowed.", parameters: Type.Object({ task: Type.String({ minLength: 1 }), wait: Type.Optional(Type.Boolean()) }, { additionalProperties: false }),
    async execute(_id, params, signal, _update, ctx) {
      if (stopped || expired()) throw new Error("Session deadline reached");
      let finish!: () => void; const done = new Promise<void>(resolve => { finish = resolve; });
      const launch = ctx.sessionManager.getEntries().find(e => e.type === "message" && e.message.role === "user");
      const launchContent = launch?.type === "message" && launch.message.role === "user" ? launch.message.content : "";
      const launchText = typeof launchContent === "string" ? launchContent : launchContent.filter(c => c.type === "text").map(c => c.text).join("\n");
      const policy = `${ctx.getSystemPrompt()}\n\nParent's original launch instructions (apply to this child too):\n${launchText}`;
      const job: Job = { id: randomUUID(), task: params.task, policy, state: "queued", text: "", done, finish };
      jobs.set(job.id, job); queue.push(job); pump();
      if (params.wait !== false) await wait(job, signal);
      return result(job);
    },
  });
  pi.registerTool({ name: "subagent_result", label: "Subagent result", description: "Poll a child by id; set wait=true to wait for completion.", parameters: Type.Object({ id: Type.String(), wait: Type.Optional(Type.Boolean()) }, { additionalProperties: false }),
    async execute(_id, params, signal) { const job = jobs.get(params.id); if (!job) throw new Error("Unknown child id"); if (params.wait) await wait(job, signal); return result(job); },
  });
  scheduleDeadline();
  pi.on("session_shutdown", async () => { if (timer) clearTimeout(timer); terminate(); await Promise.all([...jobs.values()].map(j => j.done)); });
}
