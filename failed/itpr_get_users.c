// gcc -o itpr_get_users itpr_get_users.c $(python3-config --cflags --ldflags)
#include <Python.h>

int main() {
    // Initialize the Python Interpreter
    Py_Initialize();

    // Import the module
    PyObject* pName = PyUnicode_DecodeFSDefault("get_users");
    PyObject* pModule = PyImport_Import(pName);
    Py_DECREF(pName);

    if (pModule != NULL) {
        // Get the reference to the function
        PyObject* pFunc = PyObject_GetAttrString(pModule, "get_users");
        
        // Check if the function is callable
        if (pFunc && PyCallable_Check(pFunc)) {
            // Prepare the argument to the function, if it takes one
            PyObject* pArgs = PyTuple_New(1);
            PyObject* pValue = PyUnicode_FromString("hello");
            PyTuple_SetItem(pArgs, 0, pValue);

            // Call the function
            PyObject* pResult = PyObject_CallObject(pFunc, pArgs);
            Py_DECREF(pArgs);

            if (pResult != NULL) {
                // Process the result
                printf("Call succeeded\n");
                Py_DECREF(pResult);
            } else {
                // Handle call failure
                Py_DECREF(pFunc);
                Py_DECREF(pModule);
                PyErr_Print();
                fprintf(stderr, "Call failed\n");
                return 1;
            }
        } else {
            if (PyErr_Occurred())
                PyErr_Print();
            fprintf(stderr, "Cannot find function \"get_users\"\n");
        }
        Py_XDECREF(pFunc);
        Py_DECREF(pModule);
    } else {
        PyErr_Print();
        fprintf(stderr, "Failed to load \"get_users\"\n");
        return 1;
    }
    // Clean up and shut down Python
    Py_Finalize();
    return 0;
}