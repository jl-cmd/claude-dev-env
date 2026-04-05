// TEST: Class component extending Component without React prefix (SHOULD BE CAUGHT)
import { Component } from 'react';

class MyComponent extends Component {
  render() {
    return <div>Hello</div>;
  }
}

export default MyComponent;
