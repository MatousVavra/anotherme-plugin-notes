"""Notes plugin integration tests (moved from the AnotherMe host repo,
tests/test_notes_graph.py + tests/test_plugins/test_leaf_plugins.py)."""
import os
from pathlib import Path

import pytest


@pytest.fixture
def client(make_client):
    return make_client()


def test_tree_route_returns_structure(client):
    import src.main
    from src.main import vault_manager as vm
    root = vm.vault_path(src.main.MAIN_VAULT)

    (root / "Diary" / "2025-01-01.md").write_text("# Today", encoding="utf-8")
    (root / "Stories" / "Tale.md").write_text("# A Tale", encoding="utf-8")

    resp = client.get("/plugins/notes/tree")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)

    folder_names = [entry["name"] for entry in data]
    assert "Diary" in folder_names
    assert "Stories" in folder_names

    diary_entry = next(e for e in data if e["name"] == "Diary")
    assert diary_entry["type"] == "folder"
    assert any(c["name"] == "2025-01-01.md" for c in diary_entry["children"])

    stories_entry = next(e for e in data if e["name"] == "Stories")
    assert any(c["name"] == "Tale.md" for c in stories_entry["children"])


def test_graph_route_returns_nodes_and_edges(client):
    from src.main import vault_manager as vm
    import src.main
    root = vm.vault_path(src.main.MAIN_VAULT)

    (root / "Diary" / "2025-01-01.md").write_text(
        "Today I worked on [[Test Project]].", encoding="utf-8"
    )
    (root / "Projects" / "Test Project.md").write_text(
        "# Test Project\nA project note.", encoding="utf-8"
    )

    resp = client.get("/plugins/notes/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) >= 2
    assert len(data["edges"]) >= 1


def test_graph_route_empty_vault(client):
    resp = client.get("/plugins/notes/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert data["nodes"] == []
    assert data["edges"] == []


def test_notes_list_all(client):
    vault = Path(os.environ["VAULTS_DIR"]) / "test-main"
    (vault / "Notes" / "Shopping.md").write_text("# Shopping\n\n- milk\n", encoding="utf-8")
    resp = client.get("/plugins/notes")
    assert resp.status_code == 200
    paths = [n["path"] for n in resp.json()]
    assert "Notes/Shopping.md" in paths


def test_notes_filter_folder(client):
    vault = Path(os.environ["VAULTS_DIR"]) / "test-main"
    (vault / "Notes" / "A.md").write_text("# A\n", encoding="utf-8")
    resp = client.get("/plugins/notes", params={"folder": "diary"})
    assert all(n["folder"].lower() == "diary" for n in resp.json())


def test_notes_search(client):
    vault = Path(os.environ["VAULTS_DIR"]) / "test-main"
    (vault / "Notes" / "Trip plan.md").write_text("# Trip\n", encoding="utf-8")
    resp = client.get("/plugins/notes", params={"search": "trip"})
    assert any("Trip" in n["filename"] for n in resp.json())


def test_notes_read(client):
    vault = Path(os.environ["VAULTS_DIR"]) / "test-main"
    (vault / "Notes" / "Hello.md").write_text("# Hello\n\nworld\n", encoding="utf-8")
    resp = client.get("/plugins/notes/Notes/Hello.md")
    assert resp.status_code == 200
    assert "world" in resp.json()["content"]


def test_notes_read_404(client):
    assert client.get("/plugins/notes/Notes/DoesNotExist.md").status_code == 404


def test_notes_read_rejects_traversal(client):
    secret = Path(os.environ["DATA_DIR"]) / "secret.txt"
    secret.write_text("top secret", encoding="utf-8")
    for url in ("/notes/%2E%2E/%2E%2E/secret.txt", "/plugins/notes/%2E%2E/%2E%2E/secret.txt"):
        resp = client.get(url)
        assert resp.status_code == 404, url
