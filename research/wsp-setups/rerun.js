const D = "/home/skhanxx8/projects/wsp-radiology/research/wsp-setups/";
const pre = "First read " + D + "00-research-brief.md and follow it exactly (tool rules, release-date rule, per-dataset fields, quality rules). Search via web_search with provider exa; do not ask the supervisor about tools. Budget your effort so you finish within ~40 minutes; write the output even if some entries remain uncertain. ";
const shards = [
 ["10-cxr-radiography", "YOUR SHARD: chest X-ray and other projection radiography (MSK/fracture, pediatric radiographs, dental/panoramic, portable/bedside X-ray), including multi-site/multi-country X-ray collections."],
 ["11-ct", "YOUR SHARD: CT (chest/lung nodules, abdomen/organs, oncology, head/trauma/stroke, cardiac/coronary CT, low-dose and photon-counting CT, reconstruction-kernel/multi-vendor CT, 3D segmentation and CT foundation-model benchmarks)."],
 ["12-mri", "YOUR SHARD: MRI (neuro/tumour/stroke/MS/dementia, prostate, cardiac, breast MRI, MSK knee/spine, abdominal/liver, fetal/pediatric, low-field/portable MRI, multi-vendor/field-strength collections, MRI foundation models)."]
];
const res = await runs.all(shards.map(([k, t]) => ({ key: k, agent: "researcher", model: "openai/gpt-6-luna:xhigh", task: pre + t, output: D + k + ".md" })));
return res.map((r, i) => shards[i][0] + ": ok=" + r.ok);
