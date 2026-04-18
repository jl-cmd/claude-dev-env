"""Tests for React class component validator."""

import pytest
from pathlib import Path
from .react_checks import check_no_class_components, Violation


def test_class_component_extends_component_should_fail(tmp_path: Path) -> None:
    """Class component using Component should be detected."""
    test_file = tmp_path / "BadComponent.tsx"
    test_file.write_text("""import { Component } from 'react';

class UserProfile extends Component {
    render() {
        return <div>Profile</div>;
    }
}
""")

    violations = check_no_class_components([str(test_file)])

    assert len(violations) == 1
    assert violations[0].file == str(test_file)
    assert violations[0].line == 3
    assert "class component" in violations[0].message.lower()


def test_class_component_extends_react_component_should_fail(tmp_path: Path) -> None:
    """Class component using React.Component should be detected."""
    test_file = tmp_path / "BadComponent.tsx"
    test_file.write_text("""import React from 'react';

class TaskList extends React.Component {
    render() {
        return <ul>Tasks</ul>;
    }
}
""")

    violations = check_no_class_components([str(test_file)])

    assert len(violations) == 1
    assert violations[0].file == str(test_file)
    assert violations[0].line == 3


def test_class_component_extends_purecomponent_should_fail(tmp_path: Path) -> None:
    """Class component using PureComponent should be detected."""
    test_file = tmp_path / "BadPureComponent.tsx"
    test_file.write_text("""import { PureComponent } from 'react';

class OptimizedList extends PureComponent {
    render() {
        return <ul>Items</ul>;
    }
}
""")

    violations = check_no_class_components([str(test_file)])

    assert len(violations) == 1
    assert violations[0].file == str(test_file)
    assert violations[0].line == 3
    assert "class component" in violations[0].message.lower()


def test_class_component_extends_react_purecomponent_should_fail(tmp_path: Path) -> None:
    """Class component using React.PureComponent should be detected."""
    test_file = tmp_path / "BadReactPureComponent.tsx"
    test_file.write_text("""import React from 'react';

class Dashboard extends React.PureComponent {
    render() {
        return <div>Dashboard</div>;
    }
}
""")

    violations = check_no_class_components([str(test_file)])

    assert len(violations) == 1
    assert violations[0].file == str(test_file)
    assert violations[0].line == 3
    assert "class component" in violations[0].message.lower()


def test_functional_component_should_pass(tmp_path: Path) -> None:
    """Functional components should not trigger violations."""
    test_file = tmp_path / "GoodComponent.tsx"
    test_file.write_text("""import React from 'react';

function UserProfile() {
    return <div>Profile</div>;
}

export const TaskList: React.FC = () => {
    return <ul>Tasks</ul>;
};
""")

    violations = check_no_class_components([str(test_file)])

    assert len(violations) == 0


def test_error_boundary_class_should_pass(tmp_path: Path) -> None:
    """Error boundary classes should be allowed (documented exception)."""
    test_file = tmp_path / "ErrorBoundary.tsx"
    test_file.write_text("""import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
    children: ReactNode;
}

interface State {
    hasError: boolean;
}

class ErrorBoundary extends Component<Props, State> {
    state = { hasError: false };

    static getDerivedStateFromError(): State {
        return { hasError: true };
    }

    componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
        console.error('Error caught:', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return <h1>Something went wrong.</h1>;
        }
        return this.props.children;
    }
}
""")

    violations = check_no_class_components([str(test_file)])

    assert len(violations) == 0


def test_multiple_files_with_mixed_violations(tmp_path: Path) -> None:
    """Should detect violations across multiple files."""
    good_file = tmp_path / "GoodComponent.tsx"
    good_file.write_text("""function MyComponent() {
    return <div>Good</div>;
}
""")

    bad_file1 = tmp_path / "BadComponent1.tsx"
    bad_file1.write_text("""import { Component } from 'react';

class Bad1 extends Component {
    render() { return <div>Bad</div>; }
}
""")

    bad_file2 = tmp_path / "BadComponent2.tsx"
    bad_file2.write_text("""import React from 'react';

class Bad2 extends React.Component {
    render() { return <div>Bad</div>; }
}
""")

    violations = check_no_class_components([
        str(good_file),
        str(bad_file1),
        str(bad_file2)
    ])

    assert len(violations) == 2
    assert any(str(bad_file1) in v.file for v in violations)
    assert any(str(bad_file2) in v.file for v in violations)


def test_non_react_class_should_pass(tmp_path: Path) -> None:
    """Regular TypeScript classes should not trigger violations."""
    test_file = tmp_path / "RegularClass.ts"
    test_file.write_text("""class UserService {
    fetchUser(id: string): Promise<User> {
        return fetch(`/api/users/${id}`).then(r => r.json());
    }
}

class TaskManager extends EventEmitter {
    private tasks: Task[] = [];
}
""")

    violations = check_no_class_components([str(test_file)])

    assert len(violations) == 0


def test_jsx_file_with_class_component_should_fail(tmp_path: Path) -> None:
    """Should detect class components in .jsx files too."""
    test_file = tmp_path / "OldComponent.jsx"
    test_file.write_text("""const React = require('react');

class OldComponent extends React.Component {
    render() {
        return <div>Old style</div>;
    }
}
""")

    violations = check_no_class_components([str(test_file)])

    assert len(violations) == 1
    assert violations[0].file == str(test_file)
