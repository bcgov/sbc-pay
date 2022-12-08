# Copyright © 2022 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Bring in the Tracer."""
from sbc_common_components.tracing.api_tracer import ApiTracer
from sbc_common_components.tracing.api_tracing import ApiTracing


# initialize tracer
API_TRACER = ApiTracer('BCOL API Services')
tracing = ApiTracing(  # pylint: disable=invalid-name; lower case name as used by convention in most Flask apps
    API_TRACER.tracer)
