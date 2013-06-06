from .run import RunAction
from .analysis import AnalysisAction, StatsAction, ReduceAction, ROCAction
from .net import WebAction, ClientAction
from .export import ExportAction
from .admin import AdminAction, ListAction, AddAction, ResetAction, RemoveAction, RepositoryAction, InfoAction

mdig_actions = {
    "run": RunAction,
    "analysis": AnalysisAction,
    "stats": StatsAction,
    "add": AddAction,
    "list": ListAction,
    "admin": AdminAction,
    "export": ExportAction,
    "web": WebAction,
    "node": ClientAction,
    "info": InfoAction,
    "reset": ResetAction,
    "remove": RemoveAction,
    "repository": RepositoryAction,
    "reduce": ReduceAction,
    "roc": ROCAction,
    }
