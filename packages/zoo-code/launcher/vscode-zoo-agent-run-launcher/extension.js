const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
const os = require("os");
const crypto = require("crypto");

function activate(context) {
  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  status.text = "$(rocket) Agent";
  status.tooltip = "Start read-only Zoo Agent governance intake";
  status.command = "zooAgentLauncher.startGovernanceIntake";
  status.show();
  context.subscriptions.push(status);
  context.subscriptions.push(vscode.commands.registerCommand("zooAgentLauncher.promptNow", () => promptNow(context, true)));
  context.subscriptions.push(vscode.commands.registerCommand("zooAgentLauncher.startGovernanceIntake", () => startGovernanceIntake(context)));
  context.subscriptions.push(vscode.commands.registerCommand("zooAgentLauncher.copyAgentRun", () => copyAgentRunCommand()));
  context.subscriptions.push(vscode.commands.registerCommand("zooAgentLauncher.openZooCode", () => openZooCodeBestEffort()));
  context.subscriptions.push(vscode.commands.registerCommand("zooAgentLauncher.resetWorkspacePrompt", () => resetWorkspacePrompt(context)));
  const cfg = getCfg();
  if (cfg.get("enabled", true) && cfg.get("promptMode", "oncePerWorkspace") !== "manualOnly") {
    setTimeout(() => promptNow(context, false), cfg.get("promptDelayMs", 2500));
  }
}

function deactivate() {}
function getCfg() { return vscode.workspace.getConfiguration("zooAgentLauncher"); }
function root() { const f = vscode.workspace.workspaceFolders; return f && f.length ? f[0].uri.fsPath : undefined; }
function key(r) { return "zooAgentLauncher.prompted." + crypto.createHash("sha256").update(path.resolve(r).toLowerCase()).digest("hex"); }
function isGit(r) { return !!r && fs.existsSync(path.join(r, ".git")); }
function commandPath() { return path.join(os.homedir(), ".roo", "commands", "agent-run.md"); }
function commandExists() { return fs.existsSync(commandPath()); }

async function promptNow(context, manual) {
  const cfg = getCfg(); const r = root(); if (!r) return;
  if (cfg.get("onlyGitRepos", true) && !isGit(r)) return;
  if (cfg.get("requireAgentRunCommand", true) && !commandExists()) { if (manual) vscode.window.showWarningMessage("未发现 ~/.roo/commands/agent-run.md。请先安装 Zoo Agent Governance Kit 全局配置。"); return; }
  if (!manual && cfg.get("promptMode", "oncePerWorkspace") === "oncePerWorkspace" && context.globalState.get(key(r))) return;
  const choice = await vscode.window.showInformationMessage(`检测到 Git 项目 ${path.basename(r)}。启动 Zoo Agent 治理流程？该动作只创建只读 first-run governance intake，不直接改代码。`, "启动 Zoo Agent 治理流程", "复制 /agent-run", "打开 Zoo Code", "本项目不再提示", "稍后");
  if (choice === "启动 Zoo Agent 治理流程") { await context.globalState.update(key(r), { at: new Date().toISOString(), action: "started" }); await startGovernanceIntake(context); }
  else if (choice === "复制 /agent-run") await copyAgentRunCommand();
  else if (choice === "打开 Zoo Code") await openZooCodeBestEffort();
  else if (choice === "本项目不再提示") await context.globalState.update(key(r), { at: new Date().toISOString(), action: "dismissed" });
}

function stripFrontmatter(text) { if (!text.startsWith("---")) return text; const end = text.indexOf("\n---", 3); return end === -1 ? text : text.slice(end + 4).trimStart(); }
function buildArgument() { return getCfg().get("defaultArgument", "first-run governance intake: read-only project profile discovery, no production code edits, no destructive commands, no secrets."); }
function slashText() { return `/agent-run ${buildArgument()}`; }
function expandedTask() {
  let body = slashText();
  if (commandExists()) body = stripFrontmatter(fs.readFileSync(commandPath(), "utf8")).replace(/\$ARGUMENTS/g, buildArgument());
  return `# Zoo Agent Launcher v3.7: first-run governance intake\n\nThis task is read-only by default. Initialize run ledger, discover project profile, validate global governance, detect local conflicts, and recommend next steps.\n\nSafety boundary: do not modify production code, do not run destructive commands, and do not read secrets.\n\n## Expanded /agent-run command\n\n${body}\n`;
}
async function startGovernanceIntake(context) {
  const cfg = getCfg();
  for (const id of cfg.get("zooExtensionIds", [])) {
    const ext = vscode.extensions.getExtension(id); if (!ext) continue;
    try { const api = ext.isActive ? ext.exports : await ext.activate(); if (api && typeof api.startNewTask === "function") { try { await api.startNewTask({ task: expandedTask(), newTab: cfg.get("newTab", true) }); } catch (e) { await api.startNewTask(expandedTask()); } vscode.window.showInformationMessage(`已通过 ${id} 启动只读 Zoo Agent 治理任务。`); return; } } catch (e) {}
  }
  await vscode.env.clipboard.writeText(slashText()); await openZooCodeBestEffort(); vscode.window.showWarningMessage("未能调用 Zoo/Roo startNewTask API；已复制 /agent-run first-run governance intake 指令并尝试打开 Zoo Code。请粘贴后回车。");
}
async function copyAgentRunCommand() { await vscode.env.clipboard.writeText(slashText()); vscode.window.showInformationMessage("已复制 /agent-run 指令到剪贴板。"); }
async function openZooCodeBestEffort() { for (const cmd of getCfg().get("zooOpenCommands", [])) { try { await vscode.commands.executeCommand(cmd); } catch (e) {} } }
async function resetWorkspacePrompt(context) { const r = root(); if (!r) return; await context.globalState.update(key(r), undefined); vscode.window.showInformationMessage("已重置当前 workspace 的 Zoo Agent Launcher 提示状态。"); }
module.exports = { activate, deactivate };
