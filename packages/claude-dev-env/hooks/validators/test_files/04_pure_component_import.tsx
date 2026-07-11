// TEST: PureComponent without React prefix (SHOULD BE CAUGHT but might not be)
import { PureComponent } from 'react';

class MyComponent extends PureComponent {
  render() {
    return <div>Hello</div>;
  }
}

export default MyComponent;
