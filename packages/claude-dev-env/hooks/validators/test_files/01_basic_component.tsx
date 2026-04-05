// TEST: Basic class component (SHOULD BE CAUGHT)
import React from 'react';

class MyComponent extends React.Component {
  render() {
    return <div>Hello</div>;
  }
}

export default MyComponent;
