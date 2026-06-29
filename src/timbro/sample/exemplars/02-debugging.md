# How I actually debug

I used to read the code first. Now I read the error first, then the data, then the code, in that order.

The error tells me where it broke. The data tells me what it broke on. The code only matters once I know those two things, and by then I usually already see the fix. Reading code cold, before I know what went wrong, is a good way to spend an afternoon convincing myself the bug is somewhere it isn't.

The other habit that saved me: change one thing at a time. If I touch three lines and the test goes green, I don't know which line did it, and I learned nothing. One change, one run, one piece of knowledge. It feels slow. It is faster.

Most bugs are dumb. They are a typo, an off-by-one, a stale cache, a wrong path. I assume dumb first and I am usually right.
