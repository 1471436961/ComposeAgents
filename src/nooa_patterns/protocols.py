"""The weak structural boundary shared by leaves and recursive Teams."""

from typing import Any, Protocol


class TeamMember(Protocol):
    """Complete execution contract for leaves and Teams exposing async execute.

    This is a weakly typed protocol: callers and tests ensure compatibility.
    It does not inherit NOOA's type-validation contract. When an adapter calls a
    public NOOA method, that method's native validation still applies. Any is
    limited to composition boundaries; business methods retain concrete types,
    capability descriptions and return annotations. Matching signatures do not
    imply compatible business inputs and outputs.

    Team accepts a nonempty dict of named members; a single member is valid.
    Construction shallow-copies the dict, retaining order and member references.
    Members and pattern are read-only: no additions, removals or runtime swaps.
    The closed PatternKind enum contains SEQUENTIAL, PARALLEL, ROUTER and LOOP;
    there is no third-party Pattern protocol.

    Each Team.execute first calls allocate once. Ordinary methods reuse NOOA doc
    to collect capabilities, then call a standalone @strategy generation function
    and validate its mapping from names to {task, context}. There is no implicit
    reallocation or fallback to all materials after failure. Calling allocate
    separately is a public preview without member execution; a later execute
    allocates independently. Native generation may use multiple turns/retries.
    Clear documentation helps allocation quality but does not guarantee it.

    Each member receives its own assigned task, never the predecessor's result
    as a replacement task. Each invocation gets a fresh context dict: materials
    holds the allocated context, upstream maps the direct predecessor's name to
    its result, and feedback contains {result: value} for the previous Loop
    round's final result, or is empty. The outer and runtime dicts are fresh;
    materials and results remain live references. There is no deep isolation,
    copying or resetting of members or business objects. Key presence distinguishes
    no predecessor from a predecessor returning None. Upstream history is not
    accumulated. Static materials may be allocated ahead of time; predecessors
    must explicitly carry newly produced artifacts in their business results.

    SEQUENTIAL awaits members in dict order, passing the direct predecessor's
    result through upstream, and returns the final member's result.
    PARALLEL executes independently assigned inputs concurrently with empty
    upstream/feedback. It returns a dict in member order, preserving object
    identity and None without flattening nested dicts; one member yields one item.
    ROUTER calls a synchronous selector(task, context) once after allocation using
    the Team's entry objects. A non-str result raises TypeError; an unknown name
    raises LookupError listing available names, with no default branch. Only the
    selected member executes its assigned inputs and its result is returned as-is.

    LOOP requires until/max_iterations. The limit must be a positive integer:
    bool, non-integer or missing values raise TypeError; zero/negative values
    raise ValueError. At least one complete sequential round runs. Each round
    resets upstream; later rounds give every member feedback containing only
    the previous round's final result. Assigned tasks remain unchanged across
    rounds; this Team does not replan. After each full round it calls
    until(last_result, entry_context), requiring bool or raising TypeError.
    True on the final permitted round is normal termination; False at the limit
    returns the last result. Feedback is not converted, history is not accumulated,
    no loop_exhausted field is written and no on_exhausted hook is provided.
    Applications may create a fresh until closure per invocation to observe
    rounds/last_ok and compute exhaustion after normal return. Selector/until are
    synchronous pure business decisions without LLM calls or I/O; asynchronous
    decisions belong in business members.

    The caller owns the entry context, which may be any object. The executor
    injects no fields and does not synchronize NOOA agent.context (the prompt
    block API). Local dict changes are not written back to other members, while
    mutations of shared materials may be visible. Parallel concurrency safety
    belongs to the caller. Leaves must receive local inputs through their actual
    generation-method parameters; a Python dict's existence does not prove model
    use. NOOA blocks, history and filtering can be configured through public leaf
    APIs. Root materials are not inherited automatically, and scoped context does
    not provide organization-tree isolation.

    Ordinary exceptions during allocation description, generation or structural
    validation are wrapped in AllocationError, retaining team and the original
    __cause__. Constructor, member, selector and until errors are not wrapped.
    Child allocation errors propagate unchanged, preserving the child's identity.
    CancelledError and other BaseExceptions are not wrapped. An outer
    asyncio.timeout produces TimeoutError through normal cancellation semantics;
    identifying the failure stage does not imply retryability. Sequential/Loop
    failures stop later steps. Parallel cancels unfinished siblings after observing
    a failure or member cancellation, waits for cleanup, then propagates the
    original trigger. Outer cancellation remains CancelledError; cleanup errors
    do not replace it. Errors are not grouped and partial results are not returned.
    Repeated outer cancellation may interrupt cleanup. Cancellation is cooperative
    and covers only directly awaited tasks, not independently spawned background
    tasks; fail-fast does not guarantee immediate return. The workflow is not
    retried, although native NOOA strategies may retry. Inputs, materials, Agent
    state and external side effects are not rolled back. Errors/cancellation are
    not exhaustion. There is no built-in timeout, persistence or resource shutdown.

    Leaves and Teams return business results at their own invocation boundary;
    identical Python types, shapes or task granularity are not required. None is
    an ordinary result, not a skip signal or an instruction to retain a prior value.
    Downstream members must accept the actual result shape. Child Teams retain
    their own pattern and allocate independently on every call, including each
    round of an outer Loop. Reference sharing is allowed; infinite self-recursion
    is unsupported and there is no full graph validator. A plain Team does not
    automatically provide organization-wide spans. Allocation, round progress,
    tasks and results are invocation-local; fixed configuration stays on instances.
    Concurrent calls to the same Team/member are not guaranteed safe; separate
    Agent instances simplify history isolation. Callers own Agent, model-client
    and connection lifecycles. Only public NOOA APIs are used; NOOA is not modified.
    """

    async def execute(self, task: Any, context: Any) -> Any: ...
