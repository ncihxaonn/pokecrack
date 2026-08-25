import React from "react";

function serialize(data: object): string {
  return JSON.stringify(data).replaceAll("<", "\u003c");
}

export function JsonLd({ data }: { data: object }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: serialize(data) }} />;
}
