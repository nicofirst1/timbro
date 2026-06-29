# What I look for in a review

I read a pull request twice. The first pass is for the diff. The second pass is for what the diff doesn't say.

On the first pass I check the obvious things. Does it do what the ticket asked? Are the edge cases handled? Is there a test that fails if the logic breaks? If those hold, the change is probably fine.

The second pass is the one that matters. What did this make harder to change later? What new thing now has to be kept in sync with an old thing? A new dependency, a new config knob, a new abstraction with exactly one caller. Each of these is a small tax that someone pays every day after merge.

I try to keep my comments short and specific. "This could be simpler" is useless. "You can drop this loop, the set already dedupes" is something the author can act on in a minute.
