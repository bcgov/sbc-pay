from flask_restplus import Resource, Namespace

api = Namespace('batch', description='Payment System - Batch Pay')


@api.route("")
class Batch(Resource):

    @staticmethod
    def get():
        return {"message": "batch pay"}, 200



