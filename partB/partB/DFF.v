primitive DFF_(Q, Qbar, CLK, D);
output reg Q;
input CLK;
input D;
	table
		(01)	0	:	?	:	0;
		(01)	1	:	?	:	1;
		(0?)	0	:	0	:	0;
		(0?)	1	:	1	:	1;
		(?0)	?	:	?	:	-;
		?	(??)	:	?	:	-;
	endtable
endprimitive

module DFF(Q, Qbar, CLK, D);
output Q;
output Qbar;
input CLK;
input D;

DFF_ DFF(Q, Qbar, CLK, D);
not not_(Qbar, Q);
specify
	(CLK => Q) = (1.0, 1.0);
	(CLK => Qbar) = (1.0, 1.0);
	(D => Q) = (1.0, 1.0);
	(D => Qbar) = (1.0, 1.0);
endspecify
endmodule
