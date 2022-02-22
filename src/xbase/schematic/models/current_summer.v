{{ _header }}

    {% for idx in range(_sch_params['nin'])  %}
    tran tr{{ idx }}(in[{{ idx }}], out);
    {% endfor %}

endmodule
