primitive XNOR_(OUT, A, B);
output OUT;
input A;
input B;
	table
		0	0	:	1;
		0	1	:	0;
		1	0	:	0;
		1	1	:	1;
	endtable
endprimitive

module XNOR(OUT, A, B);
output OUT;
input A;
input B;

XNOR_ XNOR(OUT, A, B);
specify
	(A => OUT) = (1.0, 1.0);
	(B => OUT) = (1.0, 1.0);
endspecify
endmodule
