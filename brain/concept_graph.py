from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

NodeType = Literal["person", "topic", "emotion", "memory", "opinion", "curiosity", "self", "event"]

TYPE_COLORS: dict[str, str] = {
    "person": "#ed64a6",
    "topic": "#4299e1",
    "emotion": "#ff8a65",
    "memory": "#9f7aea",
    "opinion": "#ecc94b",
    "curiosity": "#00d4d4",
    "self": "#f5c518",
    "event": "#68d391",
}


@dataclass
class ConceptNode:
    id: str
    label: str
    type: NodeType
    weight: float
    last_activated: float
    activation_count: int
    color: str
    notes: str
    archived: bool = False


@dataclass
class ConceptEdge:
    source: str
    target: str
    relationship: str
    strength: float
    last_fired: float


def _slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return text or f"concept-{int(time.time() * 1000)}"


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


class ConceptGraph:
    def __init__(self, base_dir: Path | str):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "state" / "concept_graph.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.nodes: dict[str, ConceptNode] = {}
        self.edges: list[ConceptEdge] = []
        self.last_updated: float = time.time()
        self.version: int = 1
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return
            self.version = int(payload.get("version", 1) or 1)
            self.last_updated = float(payload.get("last_updated") or time.time())
            for row in list(payload.get("nodes") or []):
                if not isinstance(row, dict):
                    continue
                try:
                    node = ConceptNode(
                        id=str(row.get("id") or ""),
                        label=str(row.get("label") or ""),
                        type=str(row.get("type") or "topic"),  # type: ignore[assignment]
                        weight=_clamp(float(row.get("weight") or 0.35), 0.0, 1.0),
                        last_activated=float(row.get("last_activated") or 0.0),
                        activation_count=int(row.get("activation_count") or 0),
                        color=str(row.get("color") or TYPE_COLORS.get(str(row.get("type") or "topic"), "#4299e1")),
                        notes=str(row.get("notes") or ""),
                        archived=bool(row.get("archived", False)),
                    )
                    if node.id:
                        self.nodes[node.id] = node
                except Exception:
                    continue
            for row in list(payload.get("edges") or []):
                if not isinstance(row, dict):
                    continue
                try:
                    edge = ConceptEdge(
                        source=str(row.get("source") or ""),
                        target=str(row.get("target") or ""),
                        relationship=str(row.get("relationship") or "related_to"),
                        strength=_clamp(float(row.get("strength") or 0.4), 0.0, 1.0),
                        last_fired=float(row.get("last_fired") or 0.0),
                    )
                    if edge.source and edge.target:
                        self.edges.append(edge)
                except Exception:
                    continue
        except Exception:
            return

    def _save(self) -> None:
        self.last_updated = time.time()
        payload = {
            "nodes": [asdict(n) for n in self.nodes.values()],
            "edges": [asdict(e) for e in self.edges],
            "last_updated": self.last_updated,
            "version": self.version,
        }
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def add_node(self, label: str, type: NodeType, notes: str = "") -> str:
        node_id = _slugify(label)
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.notes = notes or node.notes
            self.activate_node(node_id)
            self._save()
            return node_id
        node = ConceptNode(
            id=node_id,
            label=str(label or "").strip()[:120] or node_id,
            type=type,
            weight=0.4,
            last_activated=time.time(),
            activation_count=1,
            color=TYPE_COLORS.get(type, "#4299e1"),
            notes=str(notes or "")[:500],
        )
        self.nodes[node_id] = node
        self._save()
        return node_id

    def find_or_create(self, label: str, type: NodeType) -> str:
        slug = _slugify(label)
        if slug in self.nodes:
            self.nodes[slug].archived = False
            return slug
        return self.add_node(label, type)

    def add_edge(self, source_id: str, target_id: str, relationship: str, strength: float) -> None:
        if not source_id or not target_id or source_id not in self.nodes or target_id not in self.nodes:
            return
        rel = str(relationship or "related_to")[:64]
        strength = _clamp(strength, 0.0, 1.0)
        now = time.time()
        for edge in self.edges:
            if edge.source == source_id and edge.target == target_id and edge.relationship == rel:
                edge.strength = _clamp((edge.strength * 0.7) + (strength * 0.3), 0.0, 1.0)
                edge.last_fired = now
                self._save()
                return
        self.edges.append(
            ConceptEdge(
                source=source_id,
                target=target_id,
                relationship=rel,
                strength=strength,
                last_fired=now,
            )
        )
        self._save()

    def activate_node(self, node_id: str) -> None:
        node = self.nodes.get(node_id)
        if node is None:
            return
        node.archived = False
        node.last_activated = time.time()
        node.activation_count += 1
        node.weight = _clamp(node.weight + 0.04, 0.0, 1.0)
        self._save()

    def activate_path(self, node_ids: list[str]) -> None:
        now = time.time()
        for idx, node_id in enumerate(node_ids):
            self.activate_node(node_id)
            if idx == 0:
                continue
            prev = node_ids[idx - 1]
            for edge in self.edges:
                if edge.source == prev and edge.target == node_id:
                    edge.last_fired = now
                    edge.strength = _clamp(edge.strength + 0.02, 0.0, 1.0)
                    break
        self._save()

    def get_active_nodes(self, last_n_seconds: int = 30) -> list[dict[str, Any]]:
        cutoff = time.time() - max(1, int(last_n_seconds or 30))
        out = [asdict(node) for node in self.nodes.values() if float(node.last_activated or 0.0) >= cutoff]
        out.sort(key=lambda n: float(n.get("last_activated") or 0.0), reverse=True)
        return out

    def get_neighbors(self, node_id: str) -> list[dict[str, Any]]:
        seen: set[str] = set()
        for edge in self.edges:
            if edge.source == node_id:
                seen.add(edge.target)
            elif edge.target == node_id:
                seen.add(edge.source)
        return [asdict(self.nodes[nid]) for nid in seen if nid in self.nodes]

    def prune_old_nodes(self, max_nodes: int = 500) -> int:
        max_nodes = max(50, int(max_nodes or 500))
        if len(self.nodes) <= max_nodes:
            return 0
        ordered = sorted(
            self.nodes.values(),
            key=lambda n: (n.activation_count, n.last_activated, n.weight),
        )
        removed_ids = {n.id for n in ordered[: max(0, len(self.nodes) - max_nodes)]}
        for nid in removed_ids:
            self.nodes.pop(nid, None)
        self.edges = [e for e in self.edges if e.source not in removed_ids and e.target not in removed_ids]
        self._save()
        return len(removed_ids)

    def get_graph_data(self) -> dict[str, Any]:
        nodes = [asdict(n) for n in self.nodes.values()]
        edges = [asdict(e) for e in self.edges]
        return {
            "nodes": nodes,
            "edges": edges,
            "last_updated": self.last_updated,
            "version": self.version,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "active_nodes_30s": len(self.get_active_nodes(30)),
            },
        }

    def get_related_concepts(self, topic: str, max_hops: int = 2) -> list[dict[str, Any]]:
        start_id = _slugify(topic)
        if start_id not in self.nodes:
            # fallback: direct label match
            for nid, node in self.nodes.items():
                if node.label.strip().lower() == (topic or "").strip().lower():
                    start_id = nid
                    break
        if start_id not in self.nodes:
            return []
        max_hops = max(1, int(max_hops or 2))
        visited: set[str] = {start_id}
        queue: list[tuple[str, int, float]] = [(start_id, 0, 1.0)]
        scored: dict[str, float] = {}
        while queue:
            current, hop, path_strength = queue.pop(0)
            if hop >= max_hops:
                continue
            for edge in self.edges:
                nxt = ""
                if edge.source == current:
                    nxt = edge.target
                elif edge.target == current:
                    nxt = edge.source
                if not nxt or nxt not in self.nodes:
                    continue
                weight = path_strength * float(edge.strength or 0.0) * (0.92**hop)
                scored[nxt] = max(scored.get(nxt, 0.0), weight)
                if nxt not in visited:
                    visited.add(nxt)
                    queue.append((nxt, hop + 1, weight))
        results = []
        for nid, score in sorted(scored.items(), key=lambda kv: kv[1], reverse=True):
            if nid == start_id:
                continue
            row = asdict(self.nodes[nid])
            row["association_strength"] = round(score, 4)
            results.append(row)
        return results

    def strengthen_edge(self, source_id: str, target_id: str) -> None:
        if source_id == target_id or source_id not in self.nodes or target_id not in self.nodes:
            return
        now = time.time()
        for edge in self.edges:
            if (
                (edge.source == source_id and edge.target == target_id)
                or (edge.source == target_id and edge.target == source_id)
            ):
                edge.strength = _clamp(edge.strength + 0.05, 0.0, 1.0)
                edge.last_fired = now
                self._save()
                return
        self.edges.append(
            ConceptEdge(
                source=source_id,
                target=target_id,
                relationship="related_to",
                strength=0.45,
                last_fired=now,
            )
        )
        self._save()

    def decay_unused_nodes(self, days_threshold: int = 30) -> int:
        now = time.time()
        threshold_s = max(1, int(days_threshold or 30)) * 24 * 3600
        decayed = 0
        for node in self.nodes.values():
            age = now - float(node.last_activated or 0.0)
            if age < threshold_s:
                continue
            node.weight = _clamp(node.weight - 0.1, 0.0, 1.0)
            if node.weight < 0.1:
                node.archived = True
            decayed += 1
        if decayed:
            self._save()
        return decayed


def _safe_read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _extract_concepts_with_mistral(corpus: str) -> list[dict[str, str]]:
    if not corpus.strip():
        return []
    try:
        llm = ChatOllama(model="mistral:7b", temperature=0.2)
        result = llm.invoke(
            [
                SystemMessage(
                    content=(
                        "List the key concepts, people, topics, and themes from this conversation as a JSON array of "
                        "{label, type, relationship_to_previous} objects."
                    )
                ),
                HumanMessage(content=corpus[-6000:]),
            ]
        )
        txt = (getattr(result, "content", None) or str(result)).strip()
        left, right = txt.find("["), txt.rfind("]")
        if left < 0 or right <= left:
            return []
        arr = json.loads(txt[left : right + 1])
        out: list[dict[str, str]] = []
        for row in arr:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or "").strip()
            rtp = str(row.get("relationship_to_previous") or "related_to").strip() or "related_to"
            typ = str(row.get("type") or "topic").strip().lower()
            if typ not in TYPE_COLORS:
                typ = "topic"
            if label:
                out.append({"label": label[:120], "type": typ, "relationship_to_previous": rtp[:64]})
        return out
    except Exception:
        return []


def extract_concepts_from_text(corpus: str) -> list[dict[str, str]]:
    concepts = _extract_concepts_with_mistral(corpus)
    if concepts:
        return concepts
    # Fallback: lightweight extraction from title-cased names and nouns.
    words = re.findall(r"[A-Za-z][A-Za-z0-9_\-']{2,}", corpus or "")
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for token in words:
        label = token.strip()
        low = label.lower()
        if low in seen:
            continue
        seen.add(low)
        typ = "person" if label[:1].isupper() else "topic"
        out.append({"label": label[:120], "type": typ, "relationship_to_previous": "related_to"})
        if len(out) >= 12:
            break
    return out


def bootstrap_from_existing_memory(graph: ConceptGraph, host: dict[str, Any] | None = None) -> int:
    host = host or {}
    base_dir = Path(host.get("BASE_DIR") or graph.base_dir)
    if graph.nodes:
        return 0

    created = 0

    profiles_dir = base_dir / "profiles"
    if profiles_dir.is_dir():
        for profile_path in sorted(profiles_dir.glob("*.json")):
            data = _safe_read_json(profile_path)
            if not isinstance(data, dict):
                continue
            label = str(data.get("name") or profile_path.stem).strip()
            if not label:
                continue
            graph.find_or_create(label, "person")
            created += 1

    opinions = _safe_read_json(base_dir / "state" / "opinions.json")
    if isinstance(opinions, dict):
        for row in list(opinions.get("opinions") or []):
            if not isinstance(row, dict):
                continue
            topic = str(row.get("topic") or "").strip()
            stance = str(row.get("stance") or "").strip()
            if topic:
                graph.find_or_create(topic, "opinion")
                if stance:
                    sid = graph.find_or_create(stance, "topic")
                    tid = graph.find_or_create(topic, "opinion")
                    graph.add_edge(sid, tid, "has_opinion_on", 0.6)
                created += 1

    thoughts = _safe_read_json(base_dir / "state" / "inner_monologue.json")
    if isinstance(thoughts, dict):
        for row in list(thoughts.get("thoughts") or [])[-30:]:
            if isinstance(row, dict):
                thought = str(row.get("thought") or "").strip()
                if thought:
                    graph.find_or_create(thought[:80], "memory")
                    created += 1

    self_model = _safe_read_json(base_dir / "state" / "self_model.json")
    if isinstance(self_model, dict):
        traits = self_model.get("traits")
        if isinstance(traits, dict):
            for trait_name, trait_data in traits.items():
                notes = ""
                if isinstance(trait_data, dict):
                    notes = str(trait_data.get("description") or "")
                graph.add_node(str(trait_name), "self", notes=notes)
                created += 1

    try:
        from brain.curiosity_topics import get_current_curiosity

        cur = get_current_curiosity(host)
        if isinstance(cur, dict):
            topic = str(cur.get("topic") or "").strip()
            if topic:
                graph.find_or_create(topic, "curiosity")
                created += 1
    except Exception:
        pass

    chat_path = base_dir / "chatlog.jsonl"
    if chat_path.is_file():
        lines = chat_path.read_text(encoding="utf-8", errors="replace").splitlines()[-50:]
        corpus_rows: list[str] = []
        for line in lines:
            try:
                row = json.loads(line)
                role = str(row.get("role") or "")
                content = " ".join(str(row.get("content") or "").split()).strip()
                if content:
                    corpus_rows.append(f"{role}: {content[:240]}")
            except Exception:
                continue
        extracted = _extract_concepts_with_mistral("\n".join(corpus_rows))
        prev_id = ""
        for item in extracted:
            node_id = graph.find_or_create(item["label"], item["type"])  # type: ignore[arg-type]
            created += 1
            if prev_id and prev_id != node_id:
                graph.add_edge(prev_id, node_id, item.get("relationship_to_previous") or "related_to", 0.55)
            prev_id = node_id

    graph.prune_old_nodes(max_nodes=500)
    graph._save()
    return created

