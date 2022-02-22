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
