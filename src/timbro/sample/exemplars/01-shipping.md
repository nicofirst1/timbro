# Ship the small thing first

The best feature is the one you don't build. I learned this the slow way, after a year of maintaining code nobody asked for.

When a request comes in, I now ask one question first: does this need to exist at all? Most of the time the honest answer is no, or not yet. A flag covers it. A config value covers it. The standard library already does it and I just didn't look.

So I ship the small version. It goes out today, it does one thing, and it works. If the bigger version turns out to be real, the small one tells me what shape it should take. If it doesn't turn out to be real, I saved a week.

Boring code wins. Clever code is what someone else decodes at three in the morning when the pager goes off. I would rather write less and sleep more.
