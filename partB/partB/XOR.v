primitive XOR_(OUT, A, B);
output OUT;
input A;
input B;
	table
		0	0	:	0;
		0	1	:	1;
		1	0	:	1;
		1	1	:	0;
	endtable
endprimitive

module XOR(OUT, A, B);
output OUT;
input A;
input B;

XOR_ XOR(OUT, A, B);
specify
	(A => OUT) = (1.0, 1.0);
	(B => OUT) = (1.0, 1.0);
endspecify
endmodule
