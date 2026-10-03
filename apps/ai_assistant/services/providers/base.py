from abc import ABC, abstractmethod


class BaseAIProvider(ABC):
    def __init__(self, provider):
        self.provider = provider

    @abstractmethod
    def chat(self, messages, temperature=0.3):
        pass

    @abstractmethod
    def embedding(self, text):
        pass