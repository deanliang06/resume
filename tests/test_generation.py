from types import SimpleNamespace

import pytest

from resume_adjuster.errors import GenerationFailure
from resume_adjuster.generation import GeneratedProject, GeneratedProjectBatch, OpenAIProjectGenerator


class FakeResponses:
    def __init__(self, parsed):
        self.parsed = parsed
        self.request = None

    def parse(self, **kwargs):
        self.request = kwargs
        return SimpleNamespace(output_parsed=self.parsed)


def client_for(parsed):
    return SimpleNamespace(responses=FakeResponses(parsed))


def test_openai_generator_uses_typed_schema_and_forces_hypothetical_label():
    parsed = GeneratedProjectBatch(projects=[GeneratedProject(
        title="Queue Simulator",
        bullets=["Build a queue simulator", "Add deterministic failure tests"],
    )])
    client = client_for(parsed)
    result = OpenAIProjectGenerator(client=client).generate("Python queues", 1)
    assert client.responses.request["text_format"] is GeneratedProjectBatch
    assert result[0].title == "Queue Simulator (Hypothetical Project)"
    assert result[0].proposed is True
    assert result[0].url is None


def test_openai_generator_rejects_wrong_count():
    parsed = GeneratedProjectBatch(projects=[GeneratedProject(title="One", bullets=["Build one", "Test one"])])
    with pytest.raises(GenerationFailure, match="exactly 2"):
        OpenAIProjectGenerator(client=client_for(parsed)).generate("Python", 2)


def test_openai_generator_rejects_duplicate_bullets():
    parsed = GeneratedProjectBatch(projects=[GeneratedProject(title="One", bullets=["Build one", "Build one"])])
    with pytest.raises(GenerationFailure, match="duplicate"):
        OpenAIProjectGenerator(client=client_for(parsed)).generate("Python", 1)
