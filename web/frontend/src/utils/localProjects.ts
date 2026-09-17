// 浏览器本地项目仓库（localStorage）。
// 纯静态部署（GitHub Pages / Cloudflare / Vercel / Netlify）且未连接后端时，
// 「保存项目」走这里：项目留在当前浏览器的 localStorage 中，可随时载入/删除/继续导出 JSON。

export interface LocalProject {
  id: number;
  name: string;
  created_at: number;
  algorithms: string[];
  algo_params: Record<string, Record<string, any>>;
  x: number[];
  y: number[];
  results: Record<string, any[]>;
}

const KEY = "chromapeak_local_projects";

function readAll(): LocalProject[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const list = JSON.parse(raw);
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

function writeAll(list: LocalProject[]) {
  localStorage.setItem(KEY, JSON.stringify(list));
}

export function listLocalProjects(): LocalProject[] {
  return readAll().sort((a, b) => b.created_at - a.created_at);
}

export function getLocalProject(id: number): LocalProject | undefined {
  return readAll().find((p) => p.id === id);
}

export function saveLocalProject(
  payload: Omit<LocalProject, "id" | "created_at">
): LocalProject {
  const list = readAll();
  const proj: LocalProject = {
    ...payload,
    id: Date.now(),
    created_at: Date.now(),
  };
  list.push(proj);
  // localStorage 有 5MB 左右限制，超限时丢掉最旧的项目
  while (list.length > 1) {
    try {
      writeAll(list);
      break;
    } catch {
      list.sort((a, b) => a.created_at - b.created_at).shift();
    }
  }
  return proj;
}

export function deleteLocalProject(id: number): void {
  writeAll(readAll().filter((p) => p.id !== id));
}

export function renameLocalProject(id: number, name: string): void {
  const list = readAll();
  const hit = list.find((p) => p.id === id);
  if (hit) {
    hit.name = name;
    writeAll(list);
  }
}
