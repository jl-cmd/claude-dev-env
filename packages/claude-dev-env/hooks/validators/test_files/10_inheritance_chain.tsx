// TEST: Inheritance chain (SHOULD BE CAUGHT but won't be)
import React from 'react';

class BaseComponent extends React.Component {
  commonMethod() {
    return 'base';
  }
}

class MyComponent extends BaseComponent {
  render() {
    return <div>{this.commonMethod()}</div>;
  }
}

export default MyComponent;
