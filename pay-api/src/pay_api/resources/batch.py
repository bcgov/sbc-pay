#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Meta information about the service.

Currently this only provides API versioning information
"""

from flask_restplus import Resource, Namespace

API = Namespace('batch', description='Service - Batch Pay')


@API.route("")
class Batch(Resource):

    @staticmethod
    def get():
        return {"message": "batch pay"}, 200



