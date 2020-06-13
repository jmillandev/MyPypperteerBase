from packages.core.utils.singleton import SingletonClass
import yaml

class Config(metaclass=SingletonClass):
    _config_ = None

    def config_yaml(self):
        if not self._config_:
            config_db_file = r"./storage/config_db.yaml"
            with open(config_db_file, "r") as stream:
                config_db = yaml.load(stream)
            self._config_ = config_db
        return self._config_