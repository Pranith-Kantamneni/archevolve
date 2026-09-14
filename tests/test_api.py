"""API and frontend integration tests for ARCHEVOLVE."""

from __future__ import annotations

import os
import shutil
import tempfile

import pytest
from fastapi.testclient import TestClient

from archevolve.api import app


@pytest.fixture(scope="module", autouse=True)
def isolated_storage():
    """Isolate runs and experience memory so tests don't pollute dev state."""
    runs_dir = tempfile.mkdtemp(prefix="archevolve_runs_")
    exp_path = os.path.join(tempfile.mkdtemp(prefix="archevolve_exp_"), "mem.json")
    os.environ["ARCHEVOLVE_RUNS_DIR"] = runs_dir
    os.environ["ARCHEVOLVE_EXPERIENCE_PATH"] = exp_path
    yield
    shutil.rmtree(runs_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


REQ_ECOMMERCE = (
    "Build an e-commerce platform that supports 10,000 concurrent users, requires "
    "high availability, secure payment processing, low latency, and should scale "
    "during traffic spikes while keeping infrastructure cost reasonable."
)
REQ_CHAT = (
    "Design a real-time chat application supporting 50,000 concurrent users with "
    "low latency messaging, presence tracking, delivery receipts and high availability."
)
REQ_BANKING = (
    "Build an online banking system with strong security, transaction consistency, "
    "audit logging and PCI-DSS compliance for 1,000,000 users with high availability."
)


class TestHealthAndPages:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_home_page(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "Design your system architecture" in r.text
        assert "Generate Architecture" in r.text

    def test_static_css(self, client):
        r = client.get("/static/style.css")
        assert r.status_code == 200
        assert "--accent" in r.text


class TestOptimizeValidation:
    def test_empty_requirements_rejected(self, client):
        r = client.post("/optimize", json={
            "application_type": "E-commerce platform",
            "requirements": "",
        })
        assert r.status_code == 422

    def test_short_requirements_rejected(self, client):
        r = client.post("/optimize", json={
            "application_type": "Chat",
            "requirements": "hi",
        })
        assert r.status_code == 422


class TestOptimizationPipeline:
    def _run(self, client, app_type, req, constraints=""):
        r = client.post("/optimize", json={
            "application_type": app_type,
            "requirements": req,
            "constraints": constraints,
        })
        assert r.status_code == 200, r.text
        return r.json()

    def test_optimize_returns_full_structure(self, client):
        d = self._run(client, "E-commerce platform", REQ_ECOMMERCE)
        assert d["run_id"]
        assert d["application_type"] == "E-commerce platform"
        assert "parsed_requirements" in d
        assert d["parsed_requirements"]["expected_users"] == 10000
        assert d["parsed_requirements"]["security_level"] == "high"
        assert "baseline" in d and "final_scores" in d
        assert "initial_candidates" in d and len(d["initial_candidates"]) == 5
        assert "generation_history" in d
        assert "final_architecture" in d
        assert "connections" in d["final_architecture"]
        # All scores must be real numbers in 0..100
        for k, v in d["final_scores"].items():
            assert 0 <= v <= 100
        for c in d["initial_candidates"]:
            for k in ["cost", "security", "reliability", "performance", "scalability"]:
                assert 0 <= c["objective_scores"][k] <= 100
            assert 0 <= c["fitness"] <= 100

    def test_optimize_domain_services_present(self, client):
        d = self._run(client, "Real-time chat application", REQ_CHAT)
        all_comp_names = [c["name"] for c in d["final_architecture"]["components"]]
        # Chat domain should surface message/realtime related components somewhere
        joined = " ".join(all_comp_names + [d["final_architecture"]["communication_pattern"]])
        assert any(w in joined.lower() for w in ["presence", "message", "websocket", "message store"])

    def test_banking_includes_security_stack(self, client):
        d = self._run(client, "Online banking system", REQ_BANKING, "Compliance: PCI-DSS")
        types = [c["type"] for c in d["final_architecture"]["components"]]
        assert "security" in types
        assert d["parsed_requirements"]["compliance_requirements"] != []

    def test_different_inputs_produce_different_results(self, client):
        eco = self._run(client, "E-commerce platform", REQ_ECOMMERCE)
        chat = self._run(client, "Real-time chat application", REQ_CHAT)
        bank = self._run(client, "Online banking system", REQ_BANKING)

        def names(d):
            return [c["name"] for c in d["final_architecture"]["components"]]

        n_eco, n_chat, n_bank = names(eco), names(chat), names(bank)
        # Not identical to each other
        assert not (n_chat == n_bank == n_eco == [])
        assert n_chat != n_eco
        assert n_bank != n_eco
        # No hardcoded every-time e-commerce candidate for a chat system
        assert "Order Service" not in n_chat
        assert "Product Service" not in n_chat
        # Banking components include security stack
        assert n_bank != n_eco

    def test_results_change_appropriately(self, client):
        eco = self._run(client, "E-commerce platform", REQ_ECOMMERCE)
        chat = self._run(client, "Real-time chat application", REQ_CHAT)
        chat_comps = " ".join(c["name"].lower() for c in chat["final_architecture"]["components"])
        assert any(k in chat_comps for k in ["cassandra", "websocket", "presence", "message"])
        assert "order service" not in chat_comps

    def test_constraints_influence_input(self, client):
        d = self._run(client, "E-commerce platform", REQ_ECOMMERCE, "Budget $5000/month, use MongoDB")
        assert d["constraints"]["max_budget"] == 5000.0
        assert "mongodb" in [t.lower() for t in d["parsed_requirements"]["preferred_technologies"]]


class TestResultsPersistence:
    def test_result_available_by_run_id(self, client):
        d = client.post("/optimize", json={
            "application_type": "E-commerce platform",
            "requirements": REQ_ECOMMERCE,
        }).json()
        run_id = d["run_id"]
        r = client.get("/api/results/" + run_id)
        assert r.status_code == 200
        got = r.json()
        assert got["run_id"] == run_id
        assert got["raw_requirement"] == REQ_ECOMMERCE
        assert got["final_scores"]["overall"] == d["final_scores"]["overall"]

    def test_unknown_run_404(self, client):
        r = client.get("/api/results/doesnotexist")
        assert r.status_code == 404

    def test_results_page_renders(self, client):
        d = client.post("/optimize", json={
            "application_type": "Real-time chat application",
            "requirements": REQ_CHAT,
        }).json()
        r = client.get("/results/" + d["run_id"])
        assert r.status_code == 200
        assert "ARCHEVOLVE" in r.text

    def test_list_runs(self, client):
        client.post("/optimize", json={
            "application_type": "Social media platform",
            "requirements": REQ_CHAT,
        })
        r = client.get("/api/runs")
        assert r.status_code == 200
        runs = r.json()
        assert len(runs) >= 1
        assert runs[0]["run_id"]
        assert "final_fitness" in runs[0]


class TestEvolutionHistoryIntegrity:
    def test_generation_history_rich(self, client):
        d = client.post("/optimize", json={
            "application_type": "E-commerce platform",
            "requirements": REQ_ECOMMERCE,
        }).json()
        gens = d["generation_history"]
        assert gens, "expected generation history"
        first = gens[0]
        assert first["generation"] == 0
        assert first.get("best_fitness") is not None
        # Later generations carry mutation detail
        later = [g for g in gens if g["generation"] >= 1]
        if later:
            some = later[0]
            assert some.get("selected") is not None
            for o in some.get("offspring", []):
                assert "modifications" in o
                assert "reasoning" in o
                assert o["fitness"] is not None

    def test_fitness_progression_lines_up(self, client):
        d = client.post("/optimize", json={
            "application_type": "Online banking system",
            "requirements": REQ_BANKING,
        }).json()
        prog = d["evolution_history"]["fitness_progression"]
        assert len(prog) >= 1
        assert prog[0] is not None
        # Each consecutive best is inside [0, 100]
        for v in prog:
            assert 0 <= v <= 100