# from adaptors.pm.JIRAAdaptor import JiraAdapter
# from adaptors.pm.pm_base_adaptor import BaseAdapter
#
#
# class AdapterFactory:
#     _registry = {}
#
#     @classmethod
#     def register_adapter(cls, name: str, adapter_cls: type):
#         """
#         Register an adapter class with a unique name.
#         """
#         if not issubclass(adapter_cls, BaseAdapter):
#             raise TypeError(f"{adapter_cls} must extend BaseAdapter")
#         cls._registry[name.lower()] = adapter_cls
#         print(f"[AdapterFactory] Registered adapter: {name}")
#
#     @classmethod
#     def get_adapter(cls, name: str) -> BaseAdapter:
#         """
#         Instantiate and return the adapter by name.
#         """
#         adapter_cls = cls._registry.get(name.lower())
#         if adapter_cls is None:
#             raise ValueError(f"No adapter registered under name: {name}")
#         print(f"[AdapterFactory] Creating adapter: {name}")
#         return adapter_cls()
# AdapterFactory.register_adapter("jira", JiraAdapter)
