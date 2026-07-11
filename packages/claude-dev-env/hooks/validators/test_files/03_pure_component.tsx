// TEST: PureComponent (SHOULD BE CAUGHT but might not be)
import React from 'react';

class MyComponent extends React.PureComponent {
  render() {
    return <div>Hello</div>;
  }
}

export default MyComponent;
