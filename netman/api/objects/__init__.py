import json


class Serializable(object):
    def __init__(self, fields):
        super(Serializable, self).__init__()
        self.fields = fields

    def to_dict(self):
        return {public_key: getattr(self, public_key) for public_key in self.fields}


class Serializer(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Serializable):
            return obj.to_dict()
        else:
            return json.JSONEncoder.default(self, obj)