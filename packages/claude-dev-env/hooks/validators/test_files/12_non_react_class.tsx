// TEST: Class that extends non-React component (SHOULD BE ALLOWED)
class CustomBase {
  doSomething() {
    return 'custom';
  }
}

class MyClass extends CustomBase {
  render() {
    return this.doSomething();
  }
}

export default MyClass;
