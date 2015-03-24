/**
@ingroup B
*/

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

namespace B1 {
namespace B2 {
	void f();
	void g();
	void h();
}

void B2::f() {}

}

namespace B1 {
	void B2::g() {}
}

void B1::B2::h() {}

