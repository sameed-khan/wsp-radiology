import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import type { ExtensionAPI, BashOperations } from "@earendil-works/pi-coding-agent";
import { createReadTool, createWriteTool, createEditTool, createBashTool } from "@earendil-works/pi-coding-agent";

// The container and identity are trusted supervisor configuration, never tool arguments.
function dockerArgs(argv: string[]) {
  const container = process.env.WSP_CONTAINER;
  const user = process.env.WSP_EXEC_USER;
  if (!container || !/^[a-zA-Z0-9][a-zA-Z0-9_.-]*$/.test(container) || !user || !/^[a-zA-Z0-9_.:-]+$/.test(user)) throw new Error("Missing or invalid WSP_CONTAINER/WSP_EXEC_USER");
  return ["exec", "-i", "-u", user, "-w", "/workspace", container, ...argv];
}
function run(argv: string[], input?: string): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const child = spawn("docker", dockerArgs(argv), { stdio: ["pipe", "pipe", "pipe"] });
    const out: Buffer[] = [], err: Buffer[] = [];
    child.stdout.on("data", b => out.push(b)); child.stderr.on("data", b => err.push(b));
    child.on("error", reject);
    child.on("close", code => code === 0 ? resolve(Buffer.concat(out)) : reject(new Error(`container command failed (${code}): ${Buffer.concat(err).toString()}`)));
    child.stdin.on("error", () => {}); child.stdin.end(input);
  });
}
const readFile = (p: string) => run(["cat", "--", p]);
const writeFile = async (p: string, content: string) => { await run(["sh", "-c", 'cat > "$1"', "sh", p], content); };
const readOps = {
  readFile,
  access: async (p: string) => { await run(["test", "-r", p]); },
  detectImageMimeType: async (p: string) => {
    const b = await run(["head", "-c", "16", "--", p]);
    if (b.subarray(0, 8).equals(Buffer.from("89504e470d0a1a0a", "hex"))) return "image/png";
    if (b.subarray(0, 3).equals(Buffer.from("ffd8ff", "hex"))) return "image/jpeg";
    if (["GIF87a", "GIF89a"].includes(b.subarray(0, 6).toString())) return "image/gif";
    if (b.subarray(0, 4).toString() === "RIFF" && b.subarray(8, 12).toString() === "WEBP") return "image/webp";
    if (b.subarray(0, 2).toString() === "BM") return "image/bmp";
    return null;
  },
};
const writeOps = { writeFile, mkdir: async (p: string) => { await run(["mkdir", "-p", "--", p]); } };
const editOps = { readFile, writeFile, access: async (p: string) => { await run(["sh", "-c", 'test -r "$1" && test -w "$1"', "sh", p]); } };

const bashOps: BashOperations = {
  exec(command, _cwd, { onData, signal, timeout }) {
    return new Promise((resolve, reject) => {
      if (signal?.aborted) { reject(new Error("aborted")); return; }
      const marker = `/tmp/wsp-tool-${randomUUID()}`;
      // A session leader records its PID before executing the shell. Cancellation
      // targets that process group inside the container, not the docker client.
      const script = 'echo $$ > "$1"; shift; exec bash -c "$1"';
      const child = spawn("docker", dockerArgs(["setsid", "sh", "-c", script, "sh", marker, command]), { stdio: ["ignore", "pipe", "pipe"] });
      child.stdout.on("data", onData); child.stderr.on("data", onData);
      let cancelled = false, timedOut = false, killing: Promise<void> | undefined;
      const kill = () => {
        if (killing) return;
        cancelled = true;
        // Wait briefly for the PID file to appear if cancellation raced startup.
        killing = run(["sh", "-c", 'i=0; while [ ! -s "$1" ] && [ "$i" -lt 100 ]; do sleep .05; i=$((i+1)); done; if [ -s "$1" ]; then p=$(cat "$1"); case "$p" in *[!0-9]*|"") exit 1;; esac; kill -KILL -- "-$p" 2>/dev/null || kill -KILL "-$p" 2>/dev/null || true; rm -f -- "$1"; fi', "sh", marker]).then(() => {}, () => {});
      };
      const timer = timeout ? setTimeout(() => { timedOut = true; kill(); }, timeout * 1000) : undefined;
      signal?.addEventListener("abort", kill, { once: true });
      child.on("error", e => { if (timer) clearTimeout(timer); signal?.removeEventListener("abort", kill); reject(e); });
      child.on("close", async code => {
        if (timer) clearTimeout(timer); signal?.removeEventListener("abort", kill);
        if (killing) await killing;
        else await run(["rm", "-f", "--", marker]).catch(() => {});
        if (timedOut) reject(new Error(`timeout:${timeout}`));
        else if (cancelled) reject(new Error("aborted"));
        else resolve({ exitCode: code });
      });
    });
  },
};

export default function (pi: ExtensionAPI) {
  const tools = [createReadTool("/workspace", { operations: readOps }), createWriteTool("/workspace", { operations: writeOps }), createEditTool("/workspace", { operations: editOps }), createBashTool("/workspace", { operations: bashOps })];
  for (const tool of tools) pi.registerTool({ ...tool, execute: (id, params, signal, update) => (tool as any).execute(id, params, signal, update) } as any);
  // Never let an accidentally enabled host-side discovery tool bypass routing.
  pi.on("tool_call", async event => {
    if (["grep", "find", "ls"].includes(event.toolName)) return { block: true, reason: "Host discovery tools are disabled; use container bash instead." };
  });
  pi.on("user_bash", () => ({ operations: bashOps }));
  pi.on("before_agent_start", async event => ({ systemPrompt: event.systemPrompt.replace(`Current working directory: ${process.cwd()}`, "Current working directory: /workspace") }));
}
