We have been playing what feels like endless whack-a-mole with this system to try to get it to work. This involves things like trying to figure out why videos are out of sync or captions don't make sense, etc. And the experience has been deeply frustrating.

Moreover, it feels like we have over-engineered the application and filled it with lots of unnecessary things, especially trying to balance the back end and the front end, which are not necessarily the best design. It is common practice to use a React front end and a Python backend, and I get that. That makes sense from an abstract perspective, but it does not necessarily make sense if the software does not work.

There are plenty of Python frontends like Streamlit and Gradio and many others. 

So here's what we want to do today. First, we want to do a full code review. This will let us update the PRD and build a spec based on the existing system as it stands today. You'll need to use your code review skills and the Serena MCP to understand the codebase as it stands today.

Once you've done a review of the system and where it stands right now - MASTER-QA-REPORT-2026-02-15.md - can help - Then update these four files:

docs/prd.md
docs/spec.md (does not exist)
CLAUDE.md
README.md

After your review is complete, your next step is to use your web search tools and the fact check skill to understand what Python front ends exist that would be good replacements for the React front end, which I believe is the source of many problems. We also want to review our first principles.

| #   | Principle                    | Rule                                                                                                              |
| --- | ---------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| P1  | Fix Over Create              | Modify existing code; create only when `radon cc` ≥ C or structure mandates. No page C or lower. Never average.   |
| P2  | Reusable Testing             | No one-off scripts; single quality utility in `src/scripts/`; tests in `tests/`                                   |
| P3  | Docs Location                | All docs in `docs/`; sole exception: `CLAUDE.md` at root                                                          |
| P4  | Never Defer                  | Clean code first priority; no "fix later"; no "out of scope"; no "unrelated"; hard work now                       |
| P5  | Use Agents                   | Parallel context windows; always use for non-dependent tasks                                                      |
| P6  | Anti-Elision                 | Exhaustive generation required. Stubs/truncation/`...`/`pass`/`# TODO` prohibited                                 |
| P7  | Contextual Strictness        | Pre-authoring source inspection mandatory. Zero assumption of signatures/state. Read before write                 |
| P8  | Explicit Failure Propagation | Zero exception swallowing. Boundary validation → immediate custom exceptions. `None` signals absence, not failure |
| P9  | Idempotent Mutation          | Execution multiplicity → identical state. Verify existing state pre-mutation                                      |
| P10 | Simplicity                   | Minimum complexity for current task; no premature abstraction; no patterns unless demonstrably required           |
| P11 | Test Coverage                | 100% test coverage, 100% passing unit and E2E. < 100% = FAILURE                                                   |
| P12 | Never Reinvent the Wheel     | Prefer existing proven FOSS packages/software instead of writing new custom code                                  |

In particular, Principle 12: Never reinvent the wheel is all about using existing packages rather than engineering new solutions that are custom and difficult to maintain. Part of your review is to understand what we have built that is unnecessary, that where a FOSS package would be a better choice, Especially if we are to migrate to a Python front end and a Python backend.

We recently changed the system to go from Python 3.11 to python 3.12. What additional features does this give us access to? And how might we simplify our codebase?

This is all auditing and analysis and deep thinking and reflection and system design and design principles and anti-pattern detection. Do not implement anything. Do not write code. Do not make changes to the code base. Right now we are thinking.

You must use agent teams for this project at every step.

Every agent, at every step of the process, should be writing down their work. No agent is to think without writing and documenting their work.

Every agent is permitted to start new tasks or spawn new instances of itself to avoid running out of memory or context window. It is an antipattern to tackle one big task. It is a best practice to take a big task, break it into small tasks, accomplish each small part and write down results, then have subsequent agents compile and synthesize the findings. This ensures efficiency, effectiveness, and no loss of data.

What does it look like to move to an entirely Python application away from React EndNode on the front end? What does it look like to incorporate more existing proven packages and reduce the amount of custom code? What does it look like to simplify the workflow process? This system is not designed or intended for enterprise use or mass distribution. It is made for a single person, me, on my computer, which is a MacBook Pro. I have zsh and can install any command line tool necessary. How could we use this information to simplify our codebase further?

Begin your thinking and review. Feel free to use the brainstorming skill to ask me questions about the existing code base and what I want to accomplish so that you have as much information as you can get to successfully complete this review and help design a path forward and a piece of software that actually works.