
#pragma once

#include "./a.hpp"

/// 1
/// 2
void b(float);

void N::nf(X x) {
	(void)x;
}

void sf(N::S&);

namespace N {
	[[noreturn]]
	S nsf();
}
