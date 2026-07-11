// TEST: Error boundary + another class component in same file (OTHER CLASS SHOULD BE CAUGHT)
import React from 'react';

class ErrorBoundary extends React.Component {
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error(error, errorInfo);
  }

  render() {
    return this.props.children;
  }
}

class RegularComponent extends React.Component {
  render() {
    return <div>This should be flagged!</div>;
  }
}

export default ErrorBoundary;
