primitive DFFRS_(Q, Qbar, CLK, D, S, R);
output reg Q;
input CLK;
input D;
input S;
input R;
	table
	//	CLK		D   S   R       Q       Q'
		(01)	0	0	0	:	?	:	0;
		(01)	1	0	0	:	?	:	1;
		(0?)	0	0	0	:	0	:	0;
		(0?)	1	0	0	:	1	:	1;
		(?0)	?	0	0	:	?	:	-;
		?	(??)	0	0	:	?	:	-;
		?	?	1	0	:	?	:	1;
		?	?	0	1	:	?	:	0;
	endtable
endprimitive

module DFFRS(Q, Qbar, CLK, D, S, R);
output Q;
output Qbar;
input CLK;
input D;
input S;
input R;

DFFRS_ DFFRS(Q, Qbar, CLK, D, S, R);
not not_(Qbar, Q);
specify
	(CLK => Q) = (1.0, 1.0);
	(CLK => Qbar) = (1.0, 1.0);
	(D => Q) = (1.0, 1.0);
	(D => Qbar) = (1.0, 1.0);
	(S => Q) = (1.0, 1.0);
	(S => Qbar) = (1.0, 1.0);
	(R => Q) = (1.0, 1.0);
	(R => Qbar) = (1.0, 1.0);
endspecify
endmodule
