/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Minimal stand-in for U-Boot's include/linux/build_bug.h, providing only
 * the static_assert() which binman_sym.h uses. The full header pulls in
 * U-Boot's compiler and types headers, which the test programs do not need.
 */

#ifndef _LINUX_BUILD_BUG_H
#define _LINUX_BUILD_BUG_H

/**
 * static_assert - check integer constant expression at build time
 *
 * static_assert() is a wrapper for the C11 _Static_assert, with a
 * little macro magic to make the message optional (defaulting to the
 * stringification of the tested expression).
 */
#define static_assert(expr, ...) __static_assert(expr, ##__VA_ARGS__, #expr)
#define __static_assert(expr, msg, ...) _Static_assert(expr, msg)

#endif	/* _LINUX_BUILD_BUG_H */
