from flask_restplus import Resource, Namespace

api = Namespace('pay', description='Payment System - Pay')


@api.route("/pay")
class Pay(Resource):

    @staticmethod
    def get():
        return {"message": "pay"}, 200



