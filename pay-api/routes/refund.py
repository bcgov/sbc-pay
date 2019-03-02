from flask_restplus import Resource, Namespace

api = Namespace('refund', description='Payment System - Refund')


@api.route("")
class Refund(Resource):

    @staticmethod
    def get():
        return {"message": "refund"}, 200



