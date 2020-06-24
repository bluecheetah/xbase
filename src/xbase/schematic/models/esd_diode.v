// SPDX-License-Identifier: Apache-2.0
// Copyright 2020 Blue Cheetah Analog Design Inc.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

{{ _header }}

{% if _sch_params['dio_type'] == 'pdio' %}
always @(MINUS) begin
    if(MINUS===1'bz) $display("ESD pdio error: MINUS port is 1'bz");
{% else %}
always @(PLUS) begin
    if(PLUS===1'bz) $display("ESD ndio error: PLUS port is 1'bz");
{% endif %}
end

endmodule
