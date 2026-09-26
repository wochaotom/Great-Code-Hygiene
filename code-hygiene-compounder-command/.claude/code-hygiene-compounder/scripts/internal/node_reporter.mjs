const prefix = 'CODE_HYGIENE_TEST_EVENT=';

export default async function* report(source) {
  for await (const event of source) {
    if (event.type === 'test:pass' || event.type === 'test:fail') {
      const error = event.data.details?.error?.cause ?? event.data.details?.error;
      yield prefix + JSON.stringify({
        event: event.type,
        name: event.data.name,
        file: event.data.file,
        nesting: event.data.nesting,
        test_type: event.data.details?.type ?? event.data.type,
        skip: event.data.skip ?? event.data.details?.skip,
        todo: event.data.todo ?? event.data.details?.todo,
        error_name: error?.name,
        error_code: error?.code,
      }) + '\n';
    } else if (event.type === 'test:summary' && !event.data.file) {
      yield prefix + JSON.stringify({ event: 'test:summary', counts: event.data.counts }) + '\n';
    }
  }
}
