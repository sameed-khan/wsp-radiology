import { Type } from "typebox";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
export default function (pi: ExtensionAPI) {
  pi.registerTool({ name: "exercise_subagents", label: "Exercise subagents", description: "Exercise subagent validation, queue and deadline.", parameters: Type.Object({}),
    async execute(_id, _params, signal, _update, ctx) {
      const invalid = await ctx.executeTool("subagent", { task: "x", model: "anthropic/claude-opus-5-5" }, { signal });
      const children = [];
      for (let i = 0; i < 9; i++) children.push(await ctx.executeTool("subagent", { task: "x", wait: false }, { signal }));
      await new Promise(resolve => setTimeout(resolve, 15000));
      const results = [];
      for (const child of children) {
        const id = JSON.parse((child.result.content[0] as any).text).id;
        results.push(await ctx.executeTool("subagent_result", { id }, { signal }));
      }
      return { content: [{ type: "text", text: JSON.stringify({ invalid, children, results }) }], details: {} };
    },
  });
}
