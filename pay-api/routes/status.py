from flask_restplus import Resource, Namespace

api = Namespace('status', description='Payment System - Check Payment Status')


@api.route("")
class Status(Resource):

    @staticmethod
    def get():
        return {"message": "check status"}, 200



