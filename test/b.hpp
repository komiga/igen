
#pragma once

#include "./a.hpp"

void b(float);

void N::nf(X x) {
	(void)x;
}

void sf(N::S&);

namespace N {
	S nsf();
}
