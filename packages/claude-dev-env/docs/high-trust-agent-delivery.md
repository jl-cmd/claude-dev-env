# Building a high trust system for agent driven software delivery

Source: https://x.com/poteto/status/2102050467505430555/video/1

This document carries the model behind [`rules/correction-lens.md`](../rules/correction-lens.md).

## The central idea

Lauren's 2,000 pull requests did not come from asking agents to work faster. The number came after she built a system that let agents do useful work while she was away.

The system had several parts. The codebase showed agents the preferred patterns. Tools let agents run the product and gather evidence. Continuous integration, or CI, checked every proposed change. Rules and review bots caught repeated mistakes. Skills taught agents how to perform work in the team's preferred way. Automations connected incoming problems to agents that could investigate them.

These parts created trust over time. An agent earned more freedom by showing that it could make a change, check the result, respond to failures, and open a pull request that met the repository's standards.

The goal for a repository is clear. An agent should be able to take a task through the full path to a pull request. The repository should provide enough evidence for a merge decision without requiring a person to inspect every changed line.

## Why high volume exposes weak systems

When people first work with agents, they often watch every conversation. They correct the agent's approach, stop mistakes, and supply missing context. That works for a small number of tasks. It breaks when many agents work at the same time.

A large group of agents multiplies whatever the repository already permits. If the checks are weak, the team receives many noisy pull requests. Regressions and bugs spread faster. The team spends its time repairing agent output, and the product waits.

The answer is to build trust before adding more agents. Start with a small workflow that an agent can repeat. Watch the failures. Turn each repeated correction into a stronger control. Increase the number of agents after the controls catch the common mistakes.

The high pull request count is the result of this work. It is not the first target. The first target is a system that can check changes without waiting for one person.

## Verification gives the agent evidence

Verification asks whether the code does what the feature needs. A checkout button should complete a checkout. A changed screen should respond to the user's action. A performance change should meet a measured limit.

Teach the agent how to start the product, reach a feature, perform the relevant action, and inspect the result. The agent can collect a browser trace, a memory snapshot, a test result, or a performance measurement. The evidence should come from a repeatable procedure.

A useful verification setup has two parts. The first is a command line tool that runs the product and collects the required evidence. The second is a feature map that explains how the product works.

The command line tool gives every agent session the same procedure. Agents do not invent a new test script for every task. The tool supplies the commands, inputs, and output format. Invest in the important product paths so the tool can handle the work agents perform often.

The feature map gives the agent context that a short bug report often lacks. It describes the product's features, the paths a user takes to reach them, the controls that matter, and the expected result. Keep the map with the repository and maintain it as the product changes.

The tool and the map work together. The agent can reproduce a report, inspect the product, collect evidence, and explain the result. This turns verification into a shared team capability.

Verification does not answer every quality question. It shows that the feature works during the check. It does not by itself show that the code is easy to maintain, that the performance will stay within limits, or that the change follows the team's design rules.

Add skills for those questions. A skill can teach an agent how to debug, develop a feature, refactor code, inspect performance, or review a change. Keep the skills in a shared repository. Combine them with verification so the agent can check behavior and code quality.

Measured data makes this process stronger. Performance numbers, memory measurements, error counts, and test results give the agent something to inspect. The agent can respond to a number more reliably than to a vague instruction such as "make this faster."

## The codebase is part of the control system

Agents extend the patterns they find in the files they read. The codebase becomes working memory for the agent. An agent usually adapts an existing structure to a new task. It rarely redesigns the whole system during each pull request.

This gives the codebase a direct effect on future changes. One clear pattern reduces guessing. Several conflicting patterns force the agent to choose. The repository should make the safe choice easy to find and easy to repeat.

Start with the code structure. Change the design so that a bad pattern cannot be expressed, or so that the preferred pattern is the easiest path. Good data structures and clear boundaries can remove entire classes of errors.

Make each feature easy to locate. Define where its code lives. Define how it connects to other parts of the product. Define which parts may import each other. A clear layout gives the agent a smaller search space and fewer decisions.

The framework Lauren describes follows this idea. It sets conventions for code location and dependency boundaries. A performance problem caused by code crossing into the wrong process can become impossible through import rules. The specific framework is less important than the method. Put team knowledge into code structure so agents find it while they work.

Strict conventions may feel inconvenient to people who already know the system. They help agents and new contributors because the repository answers more questions by itself. A designer, product manager, or busy engineer can ask an agent to make a change and still benefit from the same safe paths.

## Build controls in layers

The controls work best in a clear order. Each layer handles a different kind of mistake.

First, make the mistake impossible through the code structure, architecture, or data model. This is the strongest control because the agent cannot choose the bad pattern.

Second, add static checks. Linters, compiler diagnostics, type checks, and CI inspect every proposed change. Continuous integration means that the repository runs the required checks for each pull request. When an agent repeats a mistake, turn the mistake into a check that runs every time.

Third, add rules, automated review, and skills. These explain how the team wants work done. They help with decisions that are difficult to encode in code or static checks. A rule can describe a preferred pattern. A review bot can point out a problem. A skill can give the agent a repeatable procedure.

Fourth, keep human review for judgment that the lower layers cannot express. People can decide whether a change fits the product, whether the design is sound, or whether a tradeoff is acceptable. People should not spend every review repeating the same correction that a check could catch.

Every repeated review comment is evidence that a lower layer needs improvement. Move that lesson into the code structure, a static check, CI, an automated review, or a skill. This gives the next agent the lesson without requiring a person to repeat it.

## Turn corrections into repository improvements

An agent correction should change the system when the same mistake can happen again. Fixing one pull request removes one symptom. Adding a control protects later pull requests.

Suppose an agent copies a workaround. Remove the workaround where possible. Add a rule that prevents new copies. Add a skill that explains the preferred solution. Ask an agent to clean the old copies so the repository presents better examples.

Lauren gives comments as one example. Comments can explain an edge case or a temporary workaround. In the Cursor codebase, agents began using comments as permission to keep workarounds, and the underlying problem stayed. The team chose to ban comments in Dune so agents would stop copying that pattern.

The same reasoning applies to any pattern that creates poor code. When a pattern keeps appearing, decide which control should own the correction. Put the knowledge in the repository, where every later session reads it.

This maintenance role is like gardening. Someone needs to look for small workarounds, weak patterns, and new code debt before they spread. That person removes old debt, keeps one conventional path for common work, and adds a check when a bad pattern appears.

The standard is simple. Keep the repository in a state that you would want an agent to copy. Every example teaches the next agent what to do.

## The inner delivery loop

The inner loop is the path from a task to a pull request. A dependable repository gives the agent a repeatable sequence.

1. The agent receives a task with enough context to identify the relevant feature and code.
2. The agent makes the smallest change that solves the task.
3. The agent runs the product or the relevant tests through the shared verification tools.
4. The agent collects evidence about behavior, performance, and other required limits.
5. CI, static checks, repository rules, and automated review inspect the change.
6. The agent responds to failures, repairs the change, and runs the checks again.
7. The agent opens or updates the pull request with the evidence.
8. The repository grants merge permission after the required checks pass and the remaining judgment calls are settled.

The agent earns freedom through this loop. The system does not depend on the agent saying that the change works. It depends on the agent producing evidence that the repository can inspect.

## The outer delivery loop

Work can begin outside the code editor. A message, error report, performance alert, or product signal can start the next task.

Connect an agent to the tools that hold this information. The talk mentions Slack, an error tracker, performance data, and a database service. The exact tools depend on the repository. The important point is that the agent can gather enough context to decide what happened and what task should follow.

A routine can watch a message or an alert and start an agent. The agent can reproduce the problem, make a change, run the checks, and open a pull request. Other bots can call the same verification tools, repository rules, and skills for more complex work.

This does not require one large central system. A set of small connections can start useful work. The repository supplies the controls. The agent calls the tools. CI and review inspect the result.

## How the pieces compound

Each control improves the next one. A clear code pattern gives the agent a safe starting point. The verification tool gives it product evidence. CI catches repeatable mistakes. Automated review finds code quality problems. Skills give the agent procedures for work that needs more judgment. The outer loop supplies new tasks.

Together, these controls let many agents work in parallel. The agents do not need a person to approve every small action because the environment checks the work. People can focus on product decisions, system design, and questions that the checks cannot settle.

The result is a repository where an agent with limited context can still make a good change. The environment carries the team's knowledge. The agent follows the safe paths. The pull request provides evidence for its merge decision.

## A practical way to apply the model

Start with one recurring task. Give an agent a fixed way to run the relevant part of the product and collect evidence. Record the expected result. Run the same procedure for several changes and study the failures.

When a failure repeats, ask where the correction belongs. Change the code structure if the pattern can be removed. Add a static check or CI step if the problem can be detected. Add a rule, review bot, or skill when the decision needs guidance. Improve human review when the question still needs judgment.

Keep the codebase clean as the agent population grows. Remove workarounds. Reduce competing patterns. Add one clear path for common work. Maintain the feature map and verification tools as part of the repository.

Then connect incoming signals to the same workflow. Let an agent start from a bug report or alert, reproduce the problem, make the change, run the checks, and open the pull request. Increase parallel work after the system can catch the mistakes that matter.

The key lesson is to move knowledge out of individual conversations and into the environment. A person teaches the system once. The repository, checks, tools, and skills carry that lesson into every later pull request.
