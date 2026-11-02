"""
# §3.3 LinkedIn Post Generator — instantiates GenericGeneratorAgent with linkedin_post YAML config.

Adding a new output type only requires a new YAML file in config/output_types/.
This thin wrapper exists to provide a concrete importable class for dependency injection.
"""

import anthropic

from agents.generators.base import GenericGeneratorAgent


class LinkedInPostGenerator(GenericGeneratorAgent):
    """§3.3 — LinkedIn Post generator. Config: config/output_types/linkedin_post.yaml"""

    def __init__(self, client: anthropic.AsyncAnthropic, model: str | None = None):
        kwargs = {"output_type_key": "linkedin_post", "client": client}
        if model:
            kwargs["model"] = model
        super().__init__(**kwargs)
