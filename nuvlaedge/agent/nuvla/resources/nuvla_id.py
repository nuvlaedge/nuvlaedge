class NuvlaID(str):
    @property
    def resource(self) -> str:
        return self.split("/")[0]

    @property
    def uuid(self) -> str:
        return self.split("/")[1]
