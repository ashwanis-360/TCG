from abc import ABC, abstractmethod
from typing import List, Dict, Type
from pydantic import BaseModel

from adaptors.llm.llm_config import LLMConfig


class BaseLLMAdapter(ABC):
    """Abstract base class defining the adapter interface."""
    def __init__(self, config: LLMConfig):
        self.config = config

    @abstractmethod
    def runpydetic(self, messages: List[Dict],response_model: Type[BaseModel]) -> BaseModel | None:
        """Execute an LLM chat completion call and return the content."""
        pass

    @abstractmethod
    def run(self, messages: List[Dict]) -> str:
        """Execute an LLM chat completion call and return the content."""
        pass
