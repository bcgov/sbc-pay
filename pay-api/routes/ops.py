from flask_restplus import Resource, Namespace

api = Namespace('payOPS', description='Payment System - OPS checks')


@api.route("/healthz")
class Healthz(Resource):

    @staticmethod
    def get():
        return {"message": "api is healthy"}, 200


@api.route("/readyz")
class Readyz(Resource):

    @staticmethod
    def get():
        # TODO: add a poll to the DB when called
        return {"message": "api is ready"}, 200
