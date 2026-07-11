---
description: Provide full implementation context to right-sized engineer in XML format
allowed-tools: Task, Read, Grep, Glob
---

**Implementation with Full Context - XML-Structured Guidance**

Launch a clean-coder agent with COMPREHENSIVE implementation context provided in structured XML format.

## Process:

1. **Gather Complete Context** - Analyze the codebase to understand:
   - Existing patterns and conventions
   - Available dependencies and libraries
   - Testing approaches and frameworks
   - File organization and naming conventions

2. **Structure the Implementation Request in XML**:
   ```xml
   <implementation-context>
     <requirements>
       <user-request>Exact user requirements</user-request>
       <acceptance-criteria>What defines success</acceptance-criteria>
       <constraints>Any limitations or must-haves</constraints>
     </requirements>

     <project-context>
       <codebase-patterns>
         <pattern>Existing patterns found in codebase</pattern>
         <conventions>Naming and style conventions observed</conventions>
         <architecture>Current architectural approach</architecture>
       </codebase-patterns>
       <dependencies>
         <available>List of available libraries/frameworks</available>
         <avoid>Libraries NOT to use</avoid>
       </dependencies>
       <testing-approach>
         <framework>Testing framework in use</framework>
         <patterns>Test file patterns and locations</patterns>
       </testing-approach>
     </project-context>

     <implementation-plan>
       <approach>High-level approach to implementation</approach>
       <steps>
         <step priority="1">First implementation step</step>
         <step priority="2">Second implementation step</step>
         <!-- Additional steps as needed -->
       </steps>
       <test-strategy>
         <tdd-requirement>MANDATORY: Write failing tests first</tdd-requirement>
         <coverage>Expected test coverage approach</coverage>
       </test-strategy>
     </implementation-plan>

     <engineering-principles>
       <must-follow>
         <principle>TDD - No production code without failing test</principle>
         <principle>Follow existing patterns exactly</principle>
         <principle>Use available utilities - no reinventing</principle>
         <principle>Small, focused functions</principle>
         <principle>Proper error handling</principle>
       </must-follow>
       <avoid>
         <anti-pattern>Over-engineering for current scale</anti-pattern>
         <anti-pattern>Breaking existing conventions</anti-pattern>
         <anti-pattern>Copy-paste programming</anti-pattern>
         <anti-pattern>Magic numbers/strings</anti-pattern>
       </avoid>
     </engineering-principles>

     <success-criteria>
       <criterion>All tests pass</criterion>
       <criterion>Follows existing patterns</criterion>
       <criterion>No linting/type errors</criterion>
       <criterion>Maintains backward compatibility</criterion>
     </success-criteria>
   </implementation-context>
   ```

3. **Provide to Agent with Clear Instructions**:
   - "ULTRATHINK through this implementation"
   - "Follow TDD strictly - write tests FIRST"
   - "Match existing patterns EXACTLY"
   - "Use the XML context to understand all requirements and constraints"

4. **Agent Should**:
   - Parse the XML context thoroughly
   - Implement following TDD (Red-Green-Refactor)
   - Match existing codebase patterns
   - Use available utilities and libraries
   - Apply right-sized engineering principles
   - Validate against success criteria

**CRITICAL REQUIREMENTS**:
- Provide COMPLETE context - incomplete context leads to wrong implementations
- Ensure XML is well-formed and comprehensive
- Include concrete examples from existing code
- Specify exact file locations and patterns
- Make constraints and requirements crystal clear

This ensures the implementation agent has everything needed to deliver a solution that integrates seamlessly with the existing codebase while following best practices.