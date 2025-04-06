# CMPM146_P4

Emily Jing and Glenn Grant-Richards

The heuristics used:
1. Depth Bounding:
Each agent is given a depth in the produce method.  Whenever produce is called, it is incremented.  
If it exceeds 300, it is pruned to prevent infinite recursion.
2. Cycle for already produced:
In state, we have a check for if an item is attempted to produce, while still in_production.
3. Method reversal:
We collect recipes/methods, then reverse the list of methods so that fallback methods,
such as punching for wood are tried before complicated methods.  This can avoid unnecessarily complicated processes.