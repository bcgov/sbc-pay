from flask_restplus import Resource, Namespace

API = Namespace('refunds', description='Service - Refunds')


@API.route("")
class Refund(Resource):

    @staticmethod
    def get():
        return {"message": "refund"}, 200



