const store = {
  route: "desk",
  theme: localStorage.getItem("aq-theme") || "dark",
  bookId: null,
  books: [],
  context: null,
  drawer: null,
  filters: {},
};

export default store;
