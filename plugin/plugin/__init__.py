import re as _re
from pathlib import Path as _Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel


class NoteInfo(BaseModel):
    path: str
    folder: str
    filename: str
    size: int
    modified: str


_WIKILINK_RE = _re.compile(r'\[\[([^\]]+)\]\]')


def _build_tree(root: _Path) -> list:
    result = []
    for folder in ("Diary", "Stories", "Projects", "People", "Notes", "Inbox"):
        d = root / folder
        if not d.is_dir():
            continue
        children = []
        for f in sorted(d.glob("*.md")):
            children.append({"name": f.name, "type": "file", "path": str(f.relative_to(root))})
        result.append({"name": folder, "type": "folder", "children": children})
    return result


def _build_graph(root: _Path) -> dict:
    nodes = []
    edges = []
    file_map = {}
    for folder in ("Diary", "Stories", "Projects", "People", "Notes", "Inbox"):
        d = root / folder
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            rel_path = str(f.relative_to(root))
            label = f.stem
            nodes.append({"id": rel_path, "label": label, "folder": folder})
            file_map[label.lower()] = rel_path
    for folder in ("Diary", "Stories", "Projects", "People", "Notes", "Inbox"):
        d = root / folder
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            try:
                content = f.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            rel_path = str(f.relative_to(root))
            for match in _WIKILINK_RE.finditer(content):
                target = match.group(1).strip()
                target_key = target.lower()
                if target_key in file_map:
                    target_path = file_map[target_key]
                    if target_path != rel_path:
                        edges.append({"from": rel_path, "to": target_path})
    return {"nodes": nodes, "edges": edges}


class Plugin:
    def on_load(self, ctx):
        vault = ctx.vault_manager
        router = APIRouter()

        @router.get("", response_model=list[NoteInfo])
        async def list_notes(folder: str | None = None, search: str | None = None):
            notes = vault.list_all_notes(ctx.vault_name)
            if folder:
                notes = [n for n in notes if n["folder"].lower() == folder.lower()]
            if search:
                s = search.lower()
                notes = [n for n in notes if s in n["filename"].lower() or s in n.get("path", "").lower()]
            return [NoteInfo(**n) for n in notes]

        @router.get("/tree")
        def notes_tree():
            root = vault.vault_path(ctx.vault_name)
            return _build_tree(root)

        @router.get("/graph")
        def notes_graph():
            root = vault.vault_path(ctx.vault_name)
            return _build_graph(root)

        @router.get("/{path:path}")
        async def read_note(path: str):
            root = vault.vault_path(ctx.vault_name).resolve()
            f = (root / path).resolve()
            if not f.is_file() or not f.is_relative_to(root):
                raise HTTPException(404, "Note not found")
            return {"content": f.read_text(encoding="utf-8")}

        ctx.register_router(router)
