const vscode = require("vscode");
const fs = require("fs");
const path = require("path");
const os = require("os");
const crypto = require("crypto");
const cp = require("child_process");

let progressProvider;

function activate(context) {
  progressProvider = new ProgressProvider(context);
  context.subscriptions.push(vscode.window.registerTreeDataProvider("agentGovernanceProgress", progressProvider));

  const status = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  status.text = "$(pulse) Agent";
  status.tooltip = "Agent Governance: Progress / Redirect / Resume";
  status.command = "agentGovernance.showQuickActions";
  status.show();
  context.subscriptions.push(status);

  register(context, "zooAgentLauncher.promptNow", () => promptNow(context, true));
  register(context, "zooAgentLauncher.startGovernanceIntake", () => startGovernanceIntake(context));
  register(context, "zooAgentLauncher.copyAgentRun", () => copyAgentRunCommand());
  register(context, "zooAgentLauncher.openZooCode", () => openZooCodeBestEffort());
  register(context, "zooAgentLauncher.resetWorkspacePrompt", () => resetWorkspacePrompt(context));

  register(context, "agentGovernance.showQuickActions", () => showQuickActions(context));
  register(context, "agentGovernance.showProgress", () => showProgress(context));
  register(context, "agentGovernance.openLatestProgress", () => openProgressMarkdown());
  register(context, "agentGovernance.openTaskBoard", () => openTaskBoard(context));
  register(context, "agentGovernance.applyTaskBoard", () => applyTaskBoard(context));
  register(context, "agentGovernance.runResumeSafetyCheck", () => runResumeSafetyCheck(context));
  register(context, "agentGovernance.openMergeQueue", () => openLatestArtifact("merge-queue.json"));
  register(context, "agentGovernance.openResourceLocks", () => openLatestArtifact("resource-locks.json"));
  register(context, "agentGovernance.openParallelReport", () => openLatestArtifact("parallel-execution-report.md"));
  register(context, "agentGovernance.redirectCurrentRun", () => redirectCurrentRun(context));
  register(context, "agentGovernance.copyResumeCommand", () => copyResumeCommand(context));
  register(context, "agentGovernance.stopThenSnapshot", () => stopThenSnapshot(context));
  register(context, "agentGovernance.refreshProgressTree", () => progressProvider.refresh());
  register(context, "agentGovernance.openLatestRunFolder", () => openLatestRunFolder());
  register(context, "agentGovernance.generateCodexTaskPack", () => generateCodexTaskPack(context));
  register(context, "agentGovernance.runCodexWorker", () => runCodexWorker(context));
  register(context, "agentGovernance.openCodexTaskPrompt", () => openCodexTaskPrompt());
  register(context, "agentGovernance.copyCodexTaskPrompt", () => copyCodexTaskPrompt());
  register(context, "agentGovernance.collectCodexResult", () => collectCodexResult(context));
  register(context, "agentGovernance.runCodexScopeGuard", () => runCodexScopeGuard(context));
  register(context, "agentGovernance.openCodexResult", () => openCodexResult());
  register(context, "agentGovernance.runExecutorBenchmark", () => runExecutorBenchmark(context));
  register(context, "agentGovernance.bootstrapProject", () => bootstrapProject(context));
  register(context, "agentGovernance.openBootstrapReport", () => openBootstrapReport());
  register(context, "agentGovernance.rerunBootstrap", () => rerunBootstrap(context));
  register(context, "agentGovernance.commitBootstrapFiles", () => commitBootstrapFiles());
  register(context, "agentGovernance.openProjectReadiness", () => openProjectReadiness());
  register(context, "agentGovernance.showNodeDetails", (node) => showNodeDetails(node));
  register(context, "agentGovernance.copyBranchId", (node) => copyBranchId(node));
  register(context, "agentGovernance.redirectFromBranch", (node) => redirectFromBranch(context, node));
  register(context, "agentGovernance.openWorktreePath", (node) => openWorktreePath(node));
  register(context, "agentGovernance.openProgressMarkdown", () => openProgressMarkdown());

  const watcher = vscode.workspace.createFileSystemWatcher("**/.zoo-agent/runs/**/{progress.json,run-ledger.json,branch-state.json,resource-locks.json,merge-queue.json,resume-safety-check.json,result.json,CODEX_TASK_PROMPT.md}");
  const debounced = debounce(() => progressProvider.refresh(), 500);
  watcher.onDidCreate(debounced);
  watcher.onDidChange(debounced);
  watcher.onDidDelete(debounced);
  context.subscriptions.push(watcher);

  const cfg = getCfg();
  if (cfg.get("enabled", true) && cfg.get("promptMode", "oncePerWorkspace") !== "manualOnly") {
    setTimeout(() => promptNow(context, false), cfg.get("promptDelayMs", 2500));
  }
}

function deactivate() {}

function register(context, id, fn) {
  context.subscriptions.push(vscode.commands.registerCommand(id, fn));
}

function getCfg() {
  return vscode.workspace.getConfiguration("zooAgentLauncher");
}

function root() {
  const folders = vscode.workspace.workspaceFolders;
  return folders && folders.length ? folders[0].uri.fsPath : undefined;
}

function key(workspaceRoot) {
  return "zooAgentLauncher.prompted." + crypto.createHash("sha256").update(path.resolve(workspaceRoot).toLowerCase()).digest("hex");
}

function isGit(workspaceRoot) {
  return !!workspaceRoot && fs.existsSync(path.join(workspaceRoot, ".git"));
}

function commandPath() {
  return path.join(os.homedir(), ".roo", "commands", "agent-run.md");
}

function commandExists() {
  return fs.existsSync(commandPath());
}

function scriptsRoot(context) {
  const globalScripts = path.join(os.homedir(), ".roo", "agent-governance-kit", "scripts");
  if (fs.existsSync(globalScripts)) return globalScripts;
  const localScripts = path.resolve(context.extensionPath, "..", "..", "scripts");
  return localScripts;
}

function kitRoot(context) {
  return path.resolve(scriptsRoot(context), "..");
}

function pythonCommand() {
  return getCfg().get("pythonCommand", "python");
}

function pythonCandidates() {
  const seen = new Set();
  const candidates = [];
  const add = (command, args = []) => {
    if (!command) return;
    const key = `${command}\u0000${args.join("\u0000")}`;
    if (seen.has(key)) return;
    seen.add(key);
    candidates.push({ command, args });
  };
  add(pythonCommand());
  add(process.env.ZOO_PYTHON);
  add(process.env.PYTHON);
  if (process.platform === "win32") {
    add(path.join("D:", "Anaconda", "python.exe"));
    add(path.join(os.homedir(), "Anaconda3", "python.exe"));
    add(path.join(os.homedir(), "miniconda3", "python.exe"));
    add(path.join("C:", "ProgramData", "Anaconda3", "python.exe"));
    add(path.join("C:", "ProgramData", "miniconda3", "python.exe"));
    add("python");
    add("py", ["-3"]);
  } else {
    add("python");
    add("python3");
  }
  return candidates;
}

function looksLikeMissingCommand(code, output, error) {
  if (error && error.code === "ENOENT") return true;
  if (process.platform === "win32" && code === 9009) return true;
  const text = String(output || "").toLowerCase();
  return text.includes("not recognized") || text.includes("could not find") || text.includes("python was not found");
}

function runPython(context, scriptName, args) {
  const workspaceRoot = root();
  if (!workspaceRoot) {
    return Promise.reject(new Error("No workspace folder is open."));
  }
  const script = path.join(scriptsRoot(context), scriptName);
  if (!fs.existsSync(script)) {
    return Promise.reject(new Error(`Missing governance script: ${script}`));
  }
  const candidates = pythonCandidates();
  const tried = [];
  return new Promise((resolve, reject) => {
    const tryCandidate = (index) => {
      if (index >= candidates.length) {
        reject(new Error(`No usable Python found. Tried: ${tried.join(", ")}`));
        return;
      }
      const candidate = candidates[index];
      const display = [candidate.command, ...candidate.args].join(" ");
      tried.push(display);
      const child = cp.spawn(candidate.command, [...candidate.args, script, ...args], { cwd: workspaceRoot, windowsHide: true });
      let out = "";
      let missingCommandHandled = false;
      child.stdout.on("data", (data) => { out += data.toString(); });
      child.stderr.on("data", (data) => { out += data.toString(); });
      child.on("error", (error) => {
        if (looksLikeMissingCommand(undefined, out, error)) {
          missingCommandHandled = true;
          tryCandidate(index + 1);
          return;
        }
        reject(error);
      });
      child.on("close", (code) => {
        if (missingCommandHandled) return;
        if (code === 0) {
          resolve(out);
          return;
        }
        if (looksLikeMissingCommand(code, out, undefined)) {
          tryCandidate(index + 1);
          return;
        }
        reject(new Error(out || `${scriptName} exited with ${code} via ${display}`));
      });
    };
    tryCandidate(0);
  });
}

function latestRunFolder() {
  const workspaceRoot = root();
  if (!workspaceRoot) return undefined;
  const runs = path.join(workspaceRoot, ".zoo-agent", "runs");
  if (!fs.existsSync(runs)) return undefined;
  const dirs = fs.readdirSync(runs, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(runs, entry.name))
    .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
  return dirs[0];
}

function latestProgressPath() {
  const latest = latestRunFolder();
  if (!latest) return undefined;
  return path.join(latest, "progress.json");
}

function readJson(file, fallback) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (error) {
    return fallback;
  }
}

function debounce(fn, ms) {
  let handle;
  return () => {
    clearTimeout(handle);
    handle = setTimeout(fn, ms);
  };
}

async function promptNow(context, manual) {
  const cfg = getCfg();
  const workspaceRoot = root();
  if (!workspaceRoot) return;
  if (cfg.get("onlyGitRepos", true) && !isGit(workspaceRoot)) return;
  if (cfg.get("requireAgentRunCommand", true) && !commandExists()) {
    if (manual) vscode.window.showWarningMessage("Missing ~/.roo/commands/agent-run.md. Install Zoo Agent Governance Kit global configuration first.");
    return;
  }
  if (!manual && cfg.get("promptMode", "oncePerWorkspace") === "oncePerWorkspace" && context.globalState.get(key(workspaceRoot))) return;
  const choice = await vscode.window.showInformationMessage(
    `Git workspace detected: ${path.basename(workspaceRoot)}. Start read-only Zoo Agent governance intake?`,
    "Start Governance Intake",
    "Copy /agent-run",
    "Open Zoo Code",
    "Do not ask for this workspace",
    "Later"
  );
  if (choice === "Start Governance Intake") {
    await context.globalState.update(key(workspaceRoot), { at: new Date().toISOString(), action: "started" });
    await startGovernanceIntake(context);
  } else if (choice === "Copy /agent-run") {
    await copyAgentRunCommand();
  } else if (choice === "Open Zoo Code") {
    await openZooCodeBestEffort();
  } else if (choice === "Do not ask for this workspace") {
    await context.globalState.update(key(workspaceRoot), { at: new Date().toISOString(), action: "dismissed" });
  }
}

function stripFrontmatter(text) {
  if (!text.startsWith("---")) return text;
  const end = text.indexOf("\n---", 3);
  return end === -1 ? text : text.slice(end + 4).trimStart();
}

function buildArgument() {
  return getCfg().get("defaultArgument", "first-run governance intake: read-only project profile discovery, no production code edits, no destructive commands, no secrets.");
}

function slashText() {
  return `/agent-run ${buildArgument()}`;
}

function expandedTask() {
  let body = slashText();
  if (commandExists()) {
    body = stripFrontmatter(fs.readFileSync(commandPath(), "utf8")).replace(/\$ARGUMENTS/g, buildArgument());
  }
  return `# Zoo Agent Launcher v0.3.9: first-run governance intake

This task is read-only by default. Initialize run ledger, discover project profile, validate global governance, detect local conflicts, and recommend next steps.

Safety boundary: do not modify production code, do not run destructive commands, and do not read secrets.

## Expanded /agent-run command

${body}
`;
}

async function startGovernanceIntake(context) {
  const cfg = getCfg();
  for (const id of cfg.get("zooExtensionIds", [])) {
    const ext = vscode.extensions.getExtension(id);
    if (!ext) continue;
    try {
      const api = ext.isActive ? ext.exports : await ext.activate();
      if (api && typeof api.startNewTask === "function") {
        try {
          await api.startNewTask({ task: expandedTask(), newTab: cfg.get("newTab", true) });
        } catch (error) {
          await api.startNewTask(expandedTask());
        }
        vscode.window.showInformationMessage(`Started read-only Zoo Agent governance task through ${id}.`);
        return;
      }
    } catch (error) {}
  }
  await vscode.env.clipboard.writeText(slashText());
  await openZooCodeBestEffort();
  vscode.window.showWarningMessage("Could not call Zoo/Roo startNewTask API. Copied /agent-run command and tried to open Zoo Code.");
}

async function copyAgentRunCommand() {
  await vscode.env.clipboard.writeText(slashText());
  vscode.window.showInformationMessage("Copied /agent-run command.");
}

async function openZooCodeBestEffort() {
  for (const cmd of getCfg().get("zooOpenCommands", [])) {
    try {
      await vscode.commands.executeCommand(cmd);
    } catch (error) {}
  }
}

async function resetWorkspacePrompt(context) {
  const workspaceRoot = root();
  if (!workspaceRoot) return;
  await context.globalState.update(key(workspaceRoot), undefined);
  vscode.window.showInformationMessage("Reset Zoo Agent Launcher prompt state for this workspace.");
}

async function showQuickActions(context) {
  const choice = await vscode.window.showQuickPick([
    "Show Progress Snapshot",
    "Open Progress Tree",
    "Open Task Board",
    "Apply Task Board",
    "Run Resume Safety Check",
    "Open Merge Queue",
    "Open Resource Locks",
    "Open Parallel Report",
    "Generate Codex Task Pack",
    "Run Codex Worker",
    "Open Codex Task Prompt",
    "Copy Codex Task Prompt",
    "Collect Codex Result",
    "Run Codex Scope Guard",
    "Open Codex Result",
    "Run Executor Benchmark",
    "Bootstrap Project",
    "Open Bootstrap Report",
    "Re-run Bootstrap",
    "Commit Bootstrap Files",
    "Open Project Readiness",
    "Redirect Current Run",
    "Copy Resume Command",
    "Stop Then Snapshot",
    "Refresh Agent Progress",
    "Open Latest Run Folder"
  ], { placeHolder: "Agent Governance" });
  if (choice === "Show Progress Snapshot") return showProgress(context);
  if (choice === "Open Progress Tree") return openProgressTree(context);
  if (choice === "Open Task Board") return openTaskBoard(context);
  if (choice === "Apply Task Board") return applyTaskBoard(context);
  if (choice === "Run Resume Safety Check") return runResumeSafetyCheck(context);
  if (choice === "Open Merge Queue") return openLatestArtifact("merge-queue.json");
  if (choice === "Open Resource Locks") return openLatestArtifact("resource-locks.json");
  if (choice === "Open Parallel Report") return openLatestArtifact("parallel-execution-report.md");
  if (choice === "Generate Codex Task Pack") return generateCodexTaskPack(context);
  if (choice === "Run Codex Worker") return runCodexWorker(context);
  if (choice === "Open Codex Task Prompt") return openCodexTaskPrompt();
  if (choice === "Copy Codex Task Prompt") return copyCodexTaskPrompt();
  if (choice === "Collect Codex Result") return collectCodexResult(context);
  if (choice === "Run Codex Scope Guard") return runCodexScopeGuard(context);
  if (choice === "Open Codex Result") return openCodexResult();
  if (choice === "Run Executor Benchmark") return runExecutorBenchmark(context);
  if (choice === "Bootstrap Project") return bootstrapProject(context);
  if (choice === "Open Bootstrap Report") return openBootstrapReport();
  if (choice === "Re-run Bootstrap") return rerunBootstrap(context);
  if (choice === "Commit Bootstrap Files") return commitBootstrapFiles();
  if (choice === "Open Project Readiness") return openProjectReadiness();
  if (choice === "Redirect Current Run") return redirectCurrentRun(context);
  if (choice === "Copy Resume Command") return copyResumeCommand(context);
  if (choice === "Stop Then Snapshot") return stopThenSnapshot(context);
  if (choice === "Refresh Agent Progress") return progressProvider.refresh();
  if (choice === "Open Latest Run Folder") return openLatestRunFolder();
}

async function showProgress(context) {
  try {
    await runPython(context, "generate-progress-snapshot.py", []);
    await runPython(context, "render-progress-tree.py", []);
    await runPython(context, "export-task-board.py", []);
    progressProvider.refresh();
    await openProgressMarkdown();
  } catch (error) {
    vscode.window.showErrorMessage(`Agent progress failed: ${error.message}`);
  }
}

async function openTaskBoard(context) {
  const latest = latestRunFolder();
  if (!latest || !fs.existsSync(path.join(latest, "TASKS.md"))) {
    try {
      await runPython(context, "generate-progress-snapshot.py", []);
      await runPython(context, "export-task-board.py", []);
    } catch (error) {
      vscode.window.showInformationMessage("No task board found. Run Agent: Show Progress first.");
      return;
    }
  }
  const updated = latestRunFolder();
  const target = updated ? path.join(updated, "TASKS.md") : undefined;
  if (!target || !fs.existsSync(target)) {
    vscode.window.showInformationMessage("No TASKS.md found.");
    return;
  }
  const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(target));
  await vscode.window.showTextDocument(doc, { preview: false });
}

async function applyTaskBoard(context) {
  const latest = latestRunFolder();
  if (!latest || !fs.existsSync(path.join(latest, "TASKS.md"))) {
    vscode.window.showInformationMessage("No TASKS.md found. Open or export the task board first.");
    return;
  }
  try {
    await runPython(context, "parse-task-board.py", ["--run-id", path.basename(latest)]);
    try {
      await runPython(context, "diff-task-board.py", ["--run-id", path.basename(latest)]);
    } catch (error) {
      await openLatestArtifact("task-board.diff.md");
      vscode.window.showWarningMessage("Task Board diff requires decisions before apply.");
      return;
    }
    await runPython(context, "apply-task-board.py", ["--run-id", path.basename(latest)]);
    progressProvider.refresh();
    const plan = path.join(latest, "redirect-plan.md");
    if (fs.existsSync(plan)) {
      const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(plan));
      await vscode.window.showTextDocument(doc, { preview: true });
    }
  } catch (error) {
    vscode.window.showErrorMessage(`Apply Task Board failed: ${error.message}`);
  }
}

async function runResumeSafetyCheck(context) {
  const latest = latestRunFolder();
  if (!latest) {
    vscode.window.showInformationMessage("No .zoo-agent run folder found.");
    return false;
  }
  try {
    await runPython(context, "resume-safety-check.py", ["--run-id", path.basename(latest)]);
    await openLatestArtifact("resume-safety-check.md");
    progressProvider.refresh();
    return true;
  } catch (error) {
    await openLatestArtifact("resume-safety-check.md");
    vscode.window.showWarningMessage("Resume Safety Check blocked resume. Review resume-safety-check.md.");
    return false;
  }
}

async function openProgressTree(context) {
  const latest = latestRunFolder();
  if (!latest || !fs.existsSync(path.join(latest, "progress.json"))) {
    vscode.window.showInformationMessage("No progress snapshot. Run Agent: Show Progress.");
    return;
  }
  try {
    await runPython(context, "render-progress-tree.py", []);
  } catch (error) {}
  await vscode.commands.executeCommand("agentGovernanceProgress.focus");
  progressProvider.refresh();
}

async function openProgressMarkdown() {
  const latest = latestRunFolder();
  if (!latest) {
    vscode.window.showInformationMessage("No .zoo-agent run folder found.");
    return;
  }
  const preferred = path.join(latest, "progress-tree.md");
  const fallback = path.join(latest, "progress.md");
  const target = fs.existsSync(preferred) ? preferred : fallback;
  if (!fs.existsSync(target)) {
    vscode.window.showInformationMessage("No progress markdown found. Run Agent: Show Progress.");
    return;
  }
  const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(target));
  await vscode.window.showTextDocument(doc, { preview: true });
}

async function redirectCurrentRun(context, initial) {
  const direction = await vscode.window.showInputBox({
    prompt: "Enter new direction, for example: keep backend, abandon UI, switch to Level 1 routine coding",
    value: initial || ""
  });
  if (!direction) return;
  try {
    const latest = latestRunFolder();
    const args = latest ? ["--run-id", path.basename(latest), "--direction", direction] : ["--direction", direction];
    await runPython(context, "apply-redirect-plan.py", args);
    progressProvider.refresh();
    const plan = latestRunFolder() ? path.join(latestRunFolder(), "redirect-plan.md") : undefined;
    if (plan && fs.existsSync(plan)) {
      const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(plan));
      await vscode.window.showTextDocument(doc, { preview: true });
    }
  } catch (error) {
    const command = `/redirect ${direction}`;
    await vscode.env.clipboard.writeText(command);
    await openZooCodeBestEffort();
    vscode.window.showWarningMessage("Could not apply redirect locally. Copied /redirect command for Zoo Code.");
  }
}

async function copyResumeCommand(context) {
  const latest = latestRunFolder();
  const runId = latest ? path.basename(latest) : "<run-id>";
  if (latest) {
    const ok = await runResumeSafetyCheck(context);
    if (!ok) return;
  }
  let command = `/agent-run continue run ${runId} using latest progress snapshot`;
  if (latest && fs.existsSync(path.join(latest, "redirect-plan.json"))) {
    command = `/agent-run continue run ${runId} using redirect-plan.json and latest progress snapshot`;
  }
  await vscode.env.clipboard.writeText(command);
  vscode.window.showInformationMessage("Copied resume command.");
}

async function openLatestArtifact(name) {
  const latest = latestRunFolder();
  if (!latest) {
    vscode.window.showInformationMessage("No .zoo-agent run folder found.");
    return;
  }
  const target = path.join(latest, name);
  if (!fs.existsSync(target)) {
    vscode.window.showInformationMessage(`No ${name} found for latest run.`);
    return;
  }
  const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(target));
  await vscode.window.showTextDocument(doc, { preview: true });
}

function latestCodexTaskDirs() {
  const latest = latestRunFolder();
  if (!latest) return [];
  const rootDir = path.join(latest, "codex-tasks");
  if (!fs.existsSync(rootDir)) return [];
  const dirs = [];
  for (const runEntry of fs.readdirSync(rootDir, { withFileTypes: true })) {
    const maybe = path.join(rootDir, runEntry.name);
    if (runEntry.isDirectory() && fs.existsSync(path.join(maybe, "CODEX_TASK_PROMPT.md"))) {
      dirs.push(maybe);
    }
  }
  return dirs.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
}

async function pickCodexTaskDir() {
  const dirs = latestCodexTaskDirs();
  if (!dirs.length) {
    vscode.window.showInformationMessage("No Codex Task Pack found for the latest run.");
    return undefined;
  }
  if (dirs.length === 1) return dirs[0];
  const picked = await vscode.window.showQuickPick(dirs.map((dir) => ({ label: path.basename(dir), description: dir })), { placeHolder: "Select Codex task" });
  return picked ? picked.description : undefined;
}

function readCodexTaskMeta(taskDir) {
  const meta = path.join(taskDir, "task-metadata.json");
  if (fs.existsSync(meta)) return readJson(meta, {});
  return { task_id: path.basename(taskDir), run_id: path.basename(path.dirname(path.dirname(taskDir))) };
}

async function generateCodexTaskPack(context) {
  const latest = latestRunFolder();
  const defaultRunId = latest ? path.basename(latest) : `run-${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}`;
  const runId = await vscode.window.showInputBox({ prompt: "Run id", value: defaultRunId });
  if (!runId) return;
  const taskId = await vscode.window.showInputBox({ prompt: "Task id", value: "task-001" });
  if (!taskId) return;
  const objective = await vscode.window.showInputBox({ prompt: "Objective for Codex", value: "" });
  if (!objective) return;
  const allowed = await vscode.window.showInputBox({ prompt: "Allowed files, comma-separated globs", value: "src/**,tests/**" });
  const denied = await vscode.window.showInputBox({ prompt: "Denied files, comma-separated globs", value: ".env,.env.*,**/*.pem,**/*.key,secrets/**,credentials/**" });
  const args = ["--run-id", runId, "--task-id", taskId, "--objective", objective];
  for (const item of splitCsv(allowed)) args.push("--allowed-file", item);
  for (const item of splitCsv(denied)) args.push("--denied-file", item);
  try {
    const output = await runPython(context, "generate-codex-task-pack.py", args);
    const taskDir = lastLine(output);
    const prompt = path.join(taskDir, "CODEX_TASK_PROMPT.md");
    if (fs.existsSync(prompt)) {
      const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(prompt));
      await vscode.window.showTextDocument(doc, { preview: false });
    }
    progressProvider.refresh();
  } catch (error) {
    vscode.window.showErrorMessage(`Generate Codex Task Pack failed: ${error.message}`);
  }
}

async function runCodexWorker(context) {
  const taskDir = await pickCodexTaskDir();
  const workspaceRoot = root();
  if (!taskDir || !workspaceRoot) return;
  try {
    await runPython(context, "run-codex-worker.py", ["--task-dir", taskDir, "--workspace", workspaceRoot, "--sandbox", "workspace-write"]);
    progressProvider.refresh();
    await openCodexResultOrRunFile(taskDir, "codex-run.json");
  } catch (error) {
    vscode.window.showErrorMessage(`Run Codex Worker failed: ${error.message}`);
  }
}

async function openCodexTaskPrompt() {
  const taskDir = await pickCodexTaskDir();
  if (!taskDir) return;
  const prompt = path.join(taskDir, "CODEX_TASK_PROMPT.md");
  const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(prompt));
  await vscode.window.showTextDocument(doc, { preview: false });
}

async function copyCodexTaskPrompt() {
  const taskDir = await pickCodexTaskDir();
  if (!taskDir) return;
  const prompt = path.join(taskDir, "CODEX_TASK_PROMPT.md");
  await vscode.env.clipboard.writeText(fs.readFileSync(prompt, "utf8"));
  vscode.window.showInformationMessage("Copied Codex task prompt.");
}

async function collectCodexResult(context) {
  const taskDir = await pickCodexTaskDir();
  const workspaceRoot = root();
  if (!taskDir || !workspaceRoot) return;
  const meta = readCodexTaskMeta(taskDir);
  const runId = meta.run_id || path.basename(path.dirname(path.dirname(taskDir)));
  const taskId = meta.task_id || path.basename(taskDir);
  try {
    await runPython(context, "collect-codex-result.py", ["--run-id", runId, "--task-id", taskId, "--task-dir", taskDir, "--workspace", workspaceRoot]);
    progressProvider.refresh();
    await openCodexResult();
  } catch (error) {
    vscode.window.showWarningMessage(`Collect Codex Result finished with issues: ${error.message}`);
    await openCodexResult();
  }
}

async function runCodexScopeGuard(context) {
  const taskDir = await pickCodexTaskDir();
  if (!taskDir) return;
  const meta = readCodexTaskMeta(taskDir);
  const taskId = meta.task_id || path.basename(taskDir);
  try {
    const output = await runPython(context, "check-codex-scope.py", ["--task-id", taskId, "--tasks", path.join(taskDir, "TASKS.yaml")]);
    vscode.window.showInformationMessage(`Codex scope guard passed: ${shortOutput(output)}`);
  } catch (error) {
    vscode.window.showWarningMessage(`Codex scope guard failed: ${shortOutput(error.message)}`);
  }
}

async function openCodexResult() {
  const latest = latestRunFolder();
  if (!latest) {
    vscode.window.showInformationMessage("No .zoo-agent run folder found.");
    return;
  }
  const rootDir = path.join(latest, "codex-results");
  if (!fs.existsSync(rootDir)) {
    vscode.window.showInformationMessage("No Codex result found for the latest run.");
    return;
  }
  const results = fs.readdirSync(rootDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(rootDir, entry.name, "result.md"))
    .filter((file) => fs.existsSync(file))
    .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
  if (!results.length) {
    vscode.window.showInformationMessage("No Codex result markdown found.");
    return;
  }
  const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(results[0]));
  await vscode.window.showTextDocument(doc, { preview: true });
}

async function runExecutorBenchmark(context) {
  const workspaceRoot = root();
  if (!workspaceRoot) return;
  const output = path.join(workspaceRoot, ".zoo-agent", "executor-benchmark.json");
  const score = path.join(workspaceRoot, ".zoo-agent", "executor-benchmark.score.json");
  const report = path.join(workspaceRoot, ".zoo-agent", "executor-benchmark.md");
  const cases = path.join(kitRoot(context), "evals", "executor-comparison");
  try {
    await runPython(context, "run-executor-benchmark.py", ["--case-dir", cases, "--output", output]);
    await runPython(context, "score-executor-benchmark.py", ["--input", output, "--output", score]);
    await runPython(context, "generate-executor-comparison-report.py", ["--benchmark", output, "--score", score, "--output", report]);
    const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(report));
    await vscode.window.showTextDocument(doc, { preview: true });
  } catch (error) {
    vscode.window.showErrorMessage(`Run Executor Benchmark failed: ${error.message}`);
  }
}

async function bootstrapProject(context) {
  const workspaceRoot = root();
  if (!workspaceRoot) {
    vscode.window.showInformationMessage("No workspace folder is open.");
    return;
  }
  const goal = await vscode.window.showInputBox({ prompt: "Project goal, if known", value: "" });
  const stack = await vscode.window.showInputBox({ prompt: "Project stack, if known", value: "" });
  const baseArgs = ["--project", workspaceRoot, "--mode", "auto"];
  if (goal) baseArgs.push("--goal", goal);
  if (stack) baseArgs.push("--stack", stack);
  try {
    await runPython(context, "bootstrap_project.py", [...baseArgs, "--dry-run"]);
    await openBootstrapReport();
    const choice = await vscode.window.showQuickPick([
      "Apply Safe Bootstrap Files",
      "Open Report Only",
      "Copy /agent-bootstrap Command",
      "Cancel"
    ], { placeHolder: "Project Bootstrap" });
    if (choice === "Apply Safe Bootstrap Files") {
      await runPython(context, "bootstrap_project.py", [...baseArgs, "--apply"]);
      await openBootstrapReport();
      progressProvider.refresh();
    } else if (choice === "Copy /agent-bootstrap Command") {
      await vscode.env.clipboard.writeText(`/agent-bootstrap ${goal || ""} ${stack || ""}`.trim());
      vscode.window.showInformationMessage("Copied /agent-bootstrap command.");
    }
  } catch (error) {
    vscode.window.showErrorMessage(`Project Bootstrap failed: ${error.message}`);
  }
}

async function rerunBootstrap(context) {
  const workspaceRoot = root();
  if (!workspaceRoot) return;
  try {
    await runPython(context, "bootstrap_project.py", ["--project", workspaceRoot, "--mode", "auto", "--dry-run"]);
    await openBootstrapReport();
    progressProvider.refresh();
  } catch (error) {
    vscode.window.showErrorMessage(`Re-run Bootstrap failed: ${error.message}`);
  }
}

async function openBootstrapReport() {
  const workspaceRoot = root();
  if (!workspaceRoot) return;
  await openWorkspaceFile(path.join(".zoo-agent", "bootstrap-report.md"), "No bootstrap report found. Run Agent: Bootstrap Project first.");
}

async function openProjectReadiness() {
  const workspaceRoot = root();
  if (!workspaceRoot) return;
  await openWorkspaceFile(path.join(".zoo-agent", "project-readiness.json"), "No project readiness file found. Run Agent: Bootstrap Project first.");
}

async function openWorkspaceFile(relativePath, missingMessage) {
  const workspaceRoot = root();
  const target = workspaceRoot ? path.join(workspaceRoot, relativePath) : undefined;
  if (!target || !fs.existsSync(target)) {
    vscode.window.showInformationMessage(missingMessage);
    return;
  }
  const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(target));
  await vscode.window.showTextDocument(doc, { preview: true });
}

function runShell(workspaceRoot, command, args) {
  return new Promise((resolve, reject) => {
    const child = cp.spawn(command, args, { cwd: workspaceRoot, windowsHide: true });
    let out = "";
    child.stdout.on("data", (data) => { out += data.toString(); });
    child.stderr.on("data", (data) => { out += data.toString(); });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve(out);
      else reject(new Error(out || `${command} exited with ${code}`));
    });
  });
}

async function commitBootstrapFiles() {
  const workspaceRoot = root();
  if (!workspaceRoot) return;
  try {
    const status = await runShell(workspaceRoot, "git", ["status", "--short"]);
    const diff = await runShell(workspaceRoot, "git", ["diff", "--name-only"]);
    const details = `git status --short\n${status || "(clean)"}\n\ngit diff --name-only\n${diff || "(none)"}`;
    const first = await vscode.window.showInformationMessage(details, { modal: true }, "Review and Continue", "Cancel");
    if (first !== "Review and Continue") return;
    const second = await vscode.window.showWarningMessage("Commit only bootstrap governance files with message: chore: bootstrap agent governance?", { modal: true }, "Commit Bootstrap Files", "Cancel");
    if (second !== "Commit Bootstrap Files") return;
    const paths = ["AGENTS.md", "AGENTS.md.new", ".gitignore", ".gitignore.agent.patch", ".roo", ".zoo-agent", "README.md", "TASKS.md"].filter((item) => fs.existsSync(path.join(workspaceRoot, item)));
    if (!paths.length) {
      vscode.window.showInformationMessage("No bootstrap governance files found to commit.");
      return;
    }
    await runShell(workspaceRoot, "git", ["add", ...paths]);
    await runShell(workspaceRoot, "git", ["commit", "-m", "chore: bootstrap agent governance"]);
    vscode.window.showInformationMessage("Committed bootstrap governance files. No push was run.");
  } catch (error) {
    vscode.window.showWarningMessage(`Commit Bootstrap Files failed or was not applicable: ${error.message}`);
  }
}

async function openCodexResultOrRunFile(taskDir, name) {
  const file = path.join(taskDir, name);
  if (!fs.existsSync(file)) return;
  const doc = await vscode.workspace.openTextDocument(vscode.Uri.file(file));
  await vscode.window.showTextDocument(doc, { preview: true });
}

function splitCsv(text) {
  return String(text || "").split(",").map((item) => item.trim()).filter(Boolean);
}

function lastLine(text) {
  const lines = String(text || "").trim().split(/\r?\n/).filter(Boolean);
  return lines.length ? lines[lines.length - 1].trim() : "";
}

function shortOutput(text) {
  const value = String(text || "").replace(/\s+/g, " ").trim();
  return value.length > 180 ? value.slice(0, 177) + "..." : value;
}

async function stopThenSnapshot(context) {
  const commands = await vscode.commands.getCommands(true);
  const candidates = commands.filter((cmd) => {
    const low = cmd.toLowerCase();
    return (low.includes("zoo") || low.includes("roo")) && (low.includes("stop") || low.includes("cancel")) && (low.includes("task") || low.includes("run") || low.includes("request"));
  });
  if (candidates.length) {
    try {
      await vscode.commands.executeCommand(candidates[0]);
      await wait(1000);
      await showProgress(context);
      return;
    } catch (error) {}
  }
  vscode.window.showInformationMessage("Please click the native Zoo Code Stop button first, then run Agent: Show Progress Snapshot.");
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function openLatestRunFolder() {
  const latest = latestRunFolder();
  if (!latest) {
    vscode.window.showInformationMessage("No .zoo-agent run folder found.");
    return;
  }
  await vscode.commands.executeCommand("revealFileInOS", vscode.Uri.file(latest));
}

function showNodeDetails(node) {
  if (!node || !node.raw) return;
  const raw = node.raw;
  const details = [
    `branch_id: ${raw.branch_id || ""}`,
    `status: ${raw.status || ""}`,
    `purpose: ${raw.purpose || ""}`,
    `worktree_path: ${raw.worktree_path || ""}`,
    `resource_locks: ${JSON.stringify(raw.resource_locks || raw.resource_locks_status || "")}`,
    `evidence: ${raw.evidence || ""}`,
    `quality_gate: ${raw.quality_gate || ""}`
  ].join("\n");
  vscode.window.showInformationMessage(details, { modal: true });
}

async function copyBranchId(node) {
  if (!node || !node.raw || !node.raw.branch_id) return;
  await vscode.env.clipboard.writeText(node.raw.branch_id);
  vscode.window.showInformationMessage("Copied branch id.");
}

async function redirectFromBranch(context, node) {
  const branchId = node && node.raw ? node.raw.branch_id : "";
  await redirectCurrentRun(context, branchId ? `redirect from branch ${branchId}: ` : "");
}

async function openWorktreePath(node) {
  const worktree = node && node.raw ? node.raw.worktree_path : "";
  if (!worktree) {
    vscode.window.showInformationMessage("No worktree path recorded for this node.");
    return;
  }
  await vscode.commands.executeCommand("revealFileInOS", vscode.Uri.file(worktree));
}

class ProgressProvider {
  constructor(context) {
    this.context = context;
    this._onDidChangeTreeData = new vscode.EventEmitter();
    this.onDidChangeTreeData = this._onDidChangeTreeData.event;
  }

  refresh() {
    this._onDidChangeTreeData.fire();
  }

  getTreeItem(element) {
    return element;
  }

  getChildren(element) {
    const progress = readJson(latestProgressPath() || "", undefined);
    if (!progress) {
      if (element) return [];
      return [new ProgressItem("No progress snapshot. Run Agent: Show Progress.", "welcome", vscode.TreeItemCollapsibleState.None)];
    }
    if (!element) {
      const run = new ProgressItem(
        `Run ${shortId(progress.run_id)} - ${progress.current_state || "unknown"}`,
        "run",
        vscode.TreeItemCollapsibleState.Expanded
      );
      run.description = `${progress.overall ? progress.overall.done_percent : 0}% - ${progress.overall ? progress.overall.risk_level : "unknown"}`;
      const goal = new ProgressItem("Goal", "goal", vscode.TreeItemCollapsibleState.Collapsed);
      goal.description = progress.goal_summary || progress.goal_id || "";
      return [run, goal, group("Done", progress.done), group("Pending", progress.pending), group("Risks / Unknowns", progress.risks), group("Suggested Actions", progress.suggested_redirect_commands)];
    }
    if (element.kind === "run") {
      return (progress.tree || []).map((node) => branchItem(node));
    }
    if (element.kind === "branch") {
      return (element.raw.children || []).map((node) => branchItem(node));
    }
    if (element.children) {
      return element.children;
    }
    return [];
  }
}

function shortId(value) {
  const text = String(value || "unknown");
  return text.length > 18 ? text.slice(0, 18) : text;
}

function group(label, values) {
  const item = new ProgressItem(label, "group", values && values.length ? vscode.TreeItemCollapsibleState.Collapsed : vscode.TreeItemCollapsibleState.None);
  item.children = (values || []).map((value) => new ProgressItem(String(value), "detail", vscode.TreeItemCollapsibleState.None));
  return item;
}

function branchItem(raw) {
  const item = new ProgressItem(`${statusIcon(raw.status)} ${raw.title || raw.branch_id}`, "branch", raw.children && raw.children.length ? (raw.is_active_path ? vscode.TreeItemCollapsibleState.Expanded : vscode.TreeItemCollapsibleState.Collapsed) : vscode.TreeItemCollapsibleState.None);
  item.raw = raw;
  item.description = `${raw.branch_type || "task"} - risk:${raw.risk || "unknown"} - gate:${raw.quality_gate || "unknown"}`;
  item.tooltip = [
    `branch_id: ${raw.branch_id || ""}`,
    `purpose: ${raw.purpose || ""}`,
    `worktree_path: ${raw.worktree_path || ""}`,
    `resource_locks: ${JSON.stringify(raw.resource_locks || raw.resource_locks_status || "")}`,
    `evidence: ${raw.evidence || ""}`,
    `next action: ${raw.status || "unknown"}`
  ].join("\n");
  item.contextValue = "branch";
  return item;
}

function statusIcon(status) {
  const s = String(status || "").toLowerCase();
  if (["active", "executing"].includes(s)) return "$(sync~spin)";
  if (["done", "completed", "merged", "integrated"].includes(s)) return "$(check)";
  if (["blocked", "fail", "failed"].includes(s)) return "$(error)";
  if (s === "needs_decomposition") return "$(split-horizontal)";
  if (s === "abandoned") return "$(circle-slash)";
  if (s === "redo_needed") return "$(debug-restart)";
  if (s === "retained") return "$(archive)";
  if (s === "needs_user_decision") return "$(question)";
  return "$(circle-outline)";
}

class ProgressItem extends vscode.TreeItem {
  constructor(label, kind, collapsibleState) {
    super(label, collapsibleState);
    this.kind = kind;
    this.contextValue = kind;
  }
}

module.exports = { activate, deactivate, ProgressProvider };
