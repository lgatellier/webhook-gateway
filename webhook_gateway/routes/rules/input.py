import abc
import logging
from jsonpath_ng import parse
from typing import Optional, final

from jsonpath_ng.jsonpath import DatumInContext

from ...request import WebhookRequest
from ..exceptions import RequestDoNotMatchRouteException

logger = logging.getLogger(__name__)


class InputRule:
    __metaclass__ = abc.ABCMeta

    def __init__(self, target: str, config: dict) -> None:
        self.__name = self.__class__.__name__
        self.__target = target
        self.__config = config
        if "context_variable" in config:
            self.__variable_name = config["context_variable"]
        else:
            self.__variable_name = None
        logger.debug(f"Loading rule {self.__name} with target {target}")

    @property
    def target(self) -> Optional[str]:
        return self.__target

    @property
    def config(self) -> Optional[dict]:
        return self.__config

    @property
    def variable_name(self) -> Optional[str]:
        return self.__variable_name

    @final
    def apply(self, req: WebhookRequest) -> None:
        if not self._do_apply(req):
            raise RequestDoNotMatchRouteException(self.__name, self.__target)

    @abc.abstractmethod
    def _do_apply(self, req) -> bool:
        pass


class RouteBodyInputRule(InputRule):
    __metaclass__ = abc.ABCMeta

    def __init__(self, property_json_path: str, config: dict) -> None:
        super().__init__(property_json_path, config)
        self.__json_path_expr = parse(property_json_path)

    @final
    def _do_apply(self, req: WebhookRequest) -> bool:
        matches: list[DatumInContext] = self.__json_path_expr.find(req.body)

        if self.variable_name:
            var_value = matches[0].value if len(matches) > 0 else None
            req.context.set(self.variable_name, var_value)

        return self._matches_property(matches)

    @abc.abstractmethod
    def _matches_property(self, matches: list) -> bool:
        return False


class BodyPropertyPresentInputRule(RouteBodyInputRule):
    def _matches_property(self, matches: list) -> bool:
        return len(matches) > 0


class BodyPropertyEqualsToInputRule(RouteBodyInputRule):
    def _matches_property(self, matches: list) -> bool:
        if len(matches) == 0:
            return False

        for m in matches:
            if m.value != self.config["equalsTo"]:
                return False

        return True


input_rules = {
    "present": BodyPropertyPresentInputRule,
    "equalsTo": BodyPropertyEqualsToInputRule,
}


def read_input_rule_type(key, value):
    if isinstance(value, str):
        return value
    elif isinstance(value, dict):
        if "type" in value.keys():
            return value["type"]
        elif len(value.keys()):
            return list(value.keys())[0]

    raise Exception(f"Invalid route input configuration format for key {key}")


def parse_input_rule(key: str, value) -> InputRule:
    input_rule_type = read_input_rule_type(key, value)

    if input_rule_type not in input_rules.keys():
        raise Exception(f"Unknown input check type '{input_rule_type}'")

    return input_rules[input_rule_type](key, value)
